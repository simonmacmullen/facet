#!/usr/bin/env python3

import os
import datetime
from optparse import OptionParser
import subprocess
import json
import shutil
import sys
import http.server
import multiprocessing

def main():
    parser = OptionParser(usage = "usage: %prog [options] src-images dest")
    parser.add_option("-s", "--symlink",
                      action="store_true", dest="symlink", default=False,
                      help="symlink overlay files instead of copying")
    parser.add_option("-p", "--port",
                      dest="port", default=None,
                      help="if specified, launch an HTTP server after building")
    (options, args) = parser.parse_args()
    if len(args) != 2:
        parser.print_help()
        exit(1)
    src = args[0]
    dest = args[1]
    build(src, dest, options)

def build(src, dest, options):
    print("\n Facet generator\n ---------------\n")
    os.makedirs(dest, exist_ok = True)
    copytree_over(os.path.join(os.path.dirname(sys.argv[0]), "overlay"),
                  dest, options.symlink)
    files = find_images(src)
    db_path = os.path.join(dest, "db.json")
    build_db(src, files, db_path)
    scale_all_images(src, dest, files)
    maybe_launch_http(dest, options.port)

# shutil.copytree() requires that dest not exist. grr.
def copytree_over(src, dest, create_symlinks=False):
    src = os.path.abspath(src)
    if not os.path.exists(dest):
        os.makedirs(dest)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dest, item)
        if os.path.isdir(s):
            copytree_over(s, d, create_symlinks)
        else:
            if os.path.lexists(d):
                os.remove(d)
            if create_symlinks:
                os.symlink(s, d)
            else:
                shutil.copy2(s, d)

def build_db(src, files, db_path):
    db = load_db(db_path)
    todo = todo_images_in_db(files, db)
    print(" Database: [{0}] images to update of [{1}] total".format(
        len(todo), len(files)))
    update_images_in_db(src, todo, db_path, db)
    write_db(db_path, db)
    print(" Database: written\n")

def load_db(path):
    try:
        with open(path) as f:
            return json.loads(f.read())
    except FileNotFoundError as e:
        return {}

def write_db(path, db):
    with open(path, 'w') as f:
        f.write(json.dumps(db))

def find_images(top):
    res = []
    for root, dirs, files in os.walk(top):
        for f in files:
            if plausible_image(f):
                path = os.path.join(root, f)
                rel = os.path.relpath(path, top)
                timestamp = os.path.getmtime(path)
                res.append((rel, timestamp))
    return res

def todo_images_in_db(images, db):
    return [(f, t) for (f, t) in images
            if id_from_filename(f) not in db
            or db[id_from_filename(f)]['timestamp'] != t]

def update_images_in_db(src, images, db_path, db):
    def progress(i, data):
        db[id_from_filename(data['file'])] = data
        if i % 100 == 0: # in case of ctrl-c, checkpoint every so often
            write_db(db_path, db)
    queue = [(src, f, t) for (f, t) in images]
    parallel_work(parse_image_remote, 'Database', queue, progress)

def parse_image_remote(args):
    src, filename, timestamp = args
    path = os.path.join(src, filename)
    fmt = "%[IPTC:2:25]\n%[EXIF:DateTimeOriginal]\n%[width]\n%[height]"
    cmd = ["identify", "-format", fmt, path]
    out = subprocess.check_output(cmd).decode('utf-8').splitlines()
    keywords = [k for k in out[0].split(';') if good_keyword(k)]
    taken = datetime.datetime.strptime(out[1], "%Y:%m:%d %H:%M:%S").timestamp()
    width = int(out[2])
    height = int(out[3])
    return {'file':      filename,
            'keywords':  keywords,
            'width':     width,
            'height':    height,
            'taken':     taken,
            'timestamp': timestamp}

def plausible_image(f):
    f = f.casefold()
    return f.endswith('.jpg') or f.endswith('jpeg')

def id_from_filename(f):
    return f.replace('/', '-')

def good_keyword(k):
    if k == '\\':
        return False
    return True

def scale_all_images(src, dest, files):
    scale_image_set(src, dest, files, "150")
    scale_image_set(src, dest, files, "1000")

def scale_image_set(src, dest, files, size):
    scaled = os.path.join(dest, "scaled", size)
    os.makedirs(scaled, exist_ok = True)
    todo = todo_scaled_images(scaled, files)
    print(" Images {0}: [{1}] images to scale of [{2}] total".format(
        size, len(todo), len(files)))
    scale_images(src, scaled, todo, size)
    print(" Images {0}: scaled\n".format(size))

def todo_scaled_images(scaled, images):
    return [(f, t) for (f, t) in images
            if todo_scaled_image(f, t, scaled)]

def todo_scaled_image(filename, timestamp, scaled):
    dest = os.path.join(scaled, filename)
    return not os.path.isfile(dest) or timestamp > os.path.getmtime(dest)

def scale_images(src, scaled, images, size):
    queue = [(src, scaled, f, size) for (f, _t) in images]
    parallel_work(scale_image_remote, 'Images {0}'.format(size), queue)

def scale_image_remote(args):
    src, scaled, filename, size = args
    dest = os.path.join(scaled, filename)
    os.makedirs(os.path.dirname(dest), exist_ok = True)
    cmd = ["convert", os.path.join(src, filename), "-auto-orient",
           "-thumbnail", "{0}x{1}".format(size, size), "-unsharp", "0x.5", dest]
    subprocess.check_call(cmd)

def parallel_work(work_fun, prefix, queue, progress_fun = None):
    with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
        res = pool.imap_unordered(work_fun, queue)
        for i, data in enumerate(res, 1):
            if progress_fun:
                progress_fun(i, data)
            sys.stdout.write("\r\033[K {0}: image {1}".format(prefix, i))
            sys.stdout.flush()
    sys.stdout.write("\r\033[K")

def maybe_launch_http(dest, port):
    if port:
        os.chdir(dest)
        httpd = http.server.HTTPServer(('', int(port)),
                                       http.server.SimpleHTTPRequestHandler)
        print(" Demo server running: http://localhost:{0}/".format(port))
        httpd.serve_forever()

    else:
        print(" Not starting demo HTTP server - use '--port' if you want one.")

if __name__ == "__main__":
    main()
