#!/usr/bin/env python3

import os
from datetime import datetime
from optparse import OptionParser
import subprocess
import json
import shutil
import sys
import http.server
import multiprocessing
import random
import re
import time

SCALED_SIZES = [("120", "min"), ("1000", "max")]

#-----------------------------------------------------------------------------
# Main
#-----------------------------------------------------------------------------

def main():
    parser = OptionParser(usage = "usage: %prog [options] src-images dest")
    parser.add_option("-e", "--exclude-tags",
                      dest="excludes", default="",
                      help="comma-separated list of tags which prevent a photo "
                      + "from being included")
    parser.add_option("-r", "--require-tags",
                      dest="requires", default="",
                      help="comma-separated list of tags which are required "
                      + "for a photo to be included")
    parser.add_option("-d", "--develop-mode",
                      action="store_true", dest="dev_mode", default=False,
                      help="symlink overlay files instead of copying")
    parser.add_option("-c", "--copy-originals",
                      action="store_true", dest="copy_orig", default=False,
                      help="copy source images (instead of symlinking)")
    parser.add_option("--ignore-originals",
                      action="store_true", dest="ignore_orig", default=False,
                      help="ignore source images (prevents downloads)")
    parser.add_option("-p", "--port",
                      dest="port", default=None,
                      help="if specified, launch an HTTP server after building")
    (opts, args) = parser.parse_args()
    if len(args) != 2:
        parser.print_help()
        exit(1)
    src = args[0]
    dest = args[1]
    build(src, dest, opts)

def build(src, dest, opts):
    print("\n Facet generator\n ---------------\n")
    dest_site = os.path.join(dest, "site")
    dest_json = os.path.join(dest_site, "data")
    copytree_over(os.path.join(os.path.dirname(sys.argv[0]), "overlay"),
                  dest_site, opts.dev_mode)
    files = find_images(src)
    db_path = os.path.join(dest, "db.json")
    db = build_db(src, dest_site, files, db_path, opts)
    build_db_variants(dest_json, db, opts)
    maybe_launch_http(dest_site, opts.port)

#-----------------------------------------------------------------------------
# Find images
#-----------------------------------------------------------------------------

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

def plausible_image(f):
    f = f.casefold()
    return f.endswith('.jpg') or f.endswith('jpeg')

#-----------------------------------------------------------------------------
# Build master database
#-----------------------------------------------------------------------------

def build_db(src, dest, files, db_path, opts):
    db = load_db(db_path)
    todo = todo_images(files, dest, db, opts)
    print(" To update: {0} | Total: {1}".format(len(todo), len(files)))
    update_images_in_db(src, dest, todo, db_path, db, opts)
    db = clean_db(files, db)
    write_json(db_path, db)
    db = remove_exclusions_from_db(db, opts)
    clean_scaled(db, dest, opts)
    print(" Complete\n")
    return db

def load_db(path):
    try:
        with open(path) as f:
            return json.loads(f.read())
    except FileNotFoundError as e:
        return {}

def todo_images(images, dest, db, opts):
    return [(f, t) for (f, t) in images if todo_image(f, t, dest, db, opts)]

def todo_image(file, timestamp, dest, db, opts):
    image = db.get(id_from_filename(file))
    return image is None \
        or image['timestamp'] != timestamp \
        or (todo_any_scaled_image(file, timestamp, dest, opts)
            and keep_image(image, opts))

def todo_any_scaled_image(filename, timestamp, dest, opts):
    return any([todo_scaled_image(filename, timestamp, dest, sz)
                for sz in scaled_sizes(opts)])

def todo_scaled_image(filename, timestamp, dest, size):
    scaled = scaled_filename(dest, size, filename)
    return not os.path.isfile(scaled) or timestamp > os.path.getmtime(scaled)

def clean_db(files, db):
    id_set = set([id_from_filename(f) for (f, _t) in files])
    i = 0
    keys = list(db.keys())
    for k in keys:
        if not k in id_set:
            del db[k]
            i += 1
    print(" Removed: {0}".format(i))
    return db

def remove_exclusions_from_db(db, opts):
    i = 0
    for k in list(db.keys()):
        if not keep_image(db[k], opts):
            i += 1
            del db[k]
    print(" Excluded: {0}".format(i))
    return db

def keep_image(image, opts):
    keywords = set(image['keywords'])
    requires = set(opts.requires.split(','))
    excludes = set(opts.excludes.split(','))
    return (opts.requires == '' or not keywords.isdisjoint(requires)) \
        and keywords.isdisjoint(excludes)

def clean_scaled(db, dest, opts):
    filename_set = set([image['file'] for image in db.values()])
    for size in scaled_sizes(opts):
        top = scaled_parent(dest, size)
        for root, dirs, files in os.walk(top):
            for f in files:
                fullpath = os.path.join(root, f)
                relpath = os.path.relpath(fullpath, top)
                if relpath not in filename_set:
                    os.remove(fullpath)

def update_images_in_db(src, dest, images, db_path, db, opts):
    def progress(i, data):
        if 'error' not in data:
            db[id_from_filename(data['file'])] = data
        if i % 10 == 0: # in case of ctrl-c, checkpoint every so often
            write_json(db_path, db)
    queue = [(src, dest, f, t, opts) for (f, t) in images]
    parallel_work(parse_scale_image_remote, queue, progress)

def parse_scale_image_remote(args):
    def invoke(cmd):
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
        if proc.returncode != 0 and proc.returncode != 253: # exiv2 issue 917
            raise Exception("Error code " + proc.returncode + " running " + cmd)
        return out.decode('utf-8').splitlines()
    def remove(d, k, default = None):
        if k in d:
            v = d[k]
            del d[k]
            return v
        return default

    src, dest, filename, timestamp, opts = args
    path = os.path.join(src, filename)
    out = invoke(["identify", "-format", "%[width]\n%[height]\n", path])
    width = int(out[0])
    height = int(out[1])

    exif = parse_exif(invoke(["exiv2", "-PEIXkv", path]))
    keywords = remove(exif, 'Keywords', [])
    try:
        taken = datetime.strptime(
            remove(exif, 'DateTimeOriginal'), "%Y:%m:%d %H:%M:%S")
        month = taken.strftime('%Y-%m')
        taken = int(taken.timestamp() * 1000) # Javascript expects millis
    except Exception as e:
        return {'file': filename, 'error': 'no timestamp'}
    [scale_image(src, dest, filename, sz) for sz in scaled_sizes(opts)]
    return {'id':        id_from_filename(filename),
            'file':      filename,
            'keywords':  keywords,
            'width':     width,
            'height':    height,
            'taken':     taken,
            'month':     month,
            'exif':      exif,
            'timestamp': timestamp}

GOOD_EXIF = ['DateTimeOriginal',
             'ExposureTime',
             'FNumber',
             'FocalLength',
             'FocalLengthIn35mmFilm',
             'LensMake',
             'LensModel',
             'ISOSpeedRatings',
             'Make',
             'Model']

RATIONAL_EXIF = ['ExposureTime',
                 'FNumber',
                 'FocalLength']

REPEATING_EXIF = ['Keywords']

def parse_exif(exif_list):
    exif = {}
    for item in exif_list:
        match = re.search('\w*\.\w*\.(\w*)\s*(\S.*)', item)
        if match:
            k = match.group(1)
            v = match.group(2)
            if k == 'Rating':
                k = 'Keywords'
                v = 'Rating: ' + '\u2605' * int(v)
            if k in GOOD_EXIF:
                if k in RATIONAL_EXIF:
                    (num, den) = v.split('/')
                    v = int(num) / int(den)
                exif[k] = v
            elif k in REPEATING_EXIF:
                if k not in exif:
                    exif[k] = []
                exif[k].append(v)
    return exif

def scale_image(src, dest, filename, definition):
    size, opt = definition
    s = os.path.join(src, filename)
    d = scaled_filename(dest, definition, filename)
    ensure_dir(d)
    if size == "orig":
        if opt == "symlink":
            make_symlink(s, d)
        else:
            shutil.copy2(s, d)
    else:
        suffix = "" if opt == "max" else "^"
        cmd = ["convert", s, "-auto-orient",
               "-thumbnail", "{0}x{1}{2}".format(size, size, suffix),
               "-unsharp", "0x.5", d]
        subprocess.check_call(cmd)

def id_from_filename(f):
    return f.replace('/', '-')

def scaled_filename(dest, definition, filename):
    return os.path.join(scaled_parent(dest, definition), filename)

def scaled_parent(dest, definition):
    size, _ = definition
    if size == "orig":
        return os.path.join(dest, "original")
    else:
        return os.path.join(dest, "scaled", size)

def scaled_sizes(options):
    sizes = list(SCALED_SIZES)
    if options.copy_orig:
        sizes.append(("orig", "copy"))
    elif not options.ignore_orig:
        sizes.append(("orig", "symlink"))
    return sizes

#-----------------------------------------------------------------------------
# Various sub-DBs
#-----------------------------------------------------------------------------

def build_db_variants(dest, db, opts):
    if os.path.exists(dest):
        shutil.rmtree(dest)
    key_type_to_keyword_to_image = {}

    all_images = []
    for image_id in db:
        image = db[image_id]
        for k in image['keywords']:
            add_to_indexes('keyword', k, image, key_type_to_keyword_to_image)
        add_to_indexes('month', image['month'], image, key_type_to_keyword_to_image)
        add_exif_to_indexes(image, key_type_to_keyword_to_image)
        all_images.append(image)
    sort_images(all_images)
    add_prev_next(all_images)
    key_type_to_keyword_details = {}
    for key_type in key_type_to_keyword_to_image:
        keyword_to_image = key_type_to_keyword_to_image[key_type]
        keyword_details, keyword_to_details = db_index(keyword_to_image)
        key_type_to_keyword_details[key_type] = keyword_details
        write_indexes(dest, key_type, keyword_to_details, keyword_to_image)
    index = {'keywords':  key_type_to_keyword_details,
             'originals': not opts.ignore_orig}
    write_json(os.path.join(dest, "index.json"), index)
    [write_json(os.path.join(dest, "id", "{0}.json".format(image['id'])), image)
     for image in all_images]
    write_json(os.path.join(dest, "timestamp.json"),
               {'timestamp': int(time.time())})

def add_exif_to_indexes(image, key_type_to_keyword_to_image):
    def add(our_name, exif_name):
        exif = image['exif']
        if exif_name in exif:
            add_to_indexes(our_name, exif[exif_name], image, key_type_to_keyword_to_image)
    add('camera', 'Model')
    add('lens', 'LensModel')

def add_to_indexes(key_type, keyword, image, key_type_to_keyword_to_image):
    if not key_type in key_type_to_keyword_to_image:
        key_type_to_keyword_to_image[key_type] = {}
    d = key_type_to_keyword_to_image[key_type]
    if not keyword in d:
        d[keyword] = []
    d[keyword].append(image)

def write_indexes(dest, key_type, keyword_to_details, keyword_to_image):
    for keyword in keyword_to_image:
        images = keyword_to_image[keyword]
        sort_images(images)
        write_json(os.path.join(dest, key_type,
                                "{0}.json".format(id_from_filename(keyword))),
                   {'images': images,
                    'meta':   keyword_to_details[keyword]})

def db_index(keyword_to_image):
    keyword_details = []
    for keyword in keyword_to_image:
        thumbs = [i['file'] for i in keyword_to_image[keyword]]
        random.shuffle(thumbs)
        thumbs = thumbs[0:3]
        keyword_details.append({'id':       keyword,
                                'count':    len(keyword_to_image[keyword]),
                                'thumbs':   thumbs})
    keyword_details.sort(key=lambda item: item['id'])
    add_prev_next(keyword_details)
    keyword_to_detail = {}
    for keyword_detail in keyword_details:
        keyword_to_detail[keyword_detail['id']] = keyword_detail
    return (keyword_details, keyword_to_detail)

def add_prev_next(items):
    for i in range(0, len(items)):
        if i != 0:
            items[i]['prev'] = items[i - 1]['id']
        if i != len(items) - 1:
            items[i]['next'] = items[i + 1]['id']

def sort_images(images):
    images.sort(key=lambda item: item['taken'], reverse = True)

#-----------------------------------------------------------------------------
# Utils
#-----------------------------------------------------------------------------

# shutil.copytree() requires that dest not exist. grr.
def copytree_over(src, dest, create_symlinks=False):
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
                make_symlink(s, d)
            else:
                shutil.copy2(s, d)

def write_json(path, thing):
    ensure_dir(path)
    with open(path, 'w') as f:
        f.write(json.dumps(thing))

def ensure_dir(f):
    os.makedirs(os.path.dirname(f), exist_ok = True)

def make_symlink(s, d):
    if os.path.isfile(d):
        os.remove(d)
    os.symlink(os.path.abspath(s), d)

def parallel_work(work_fun, queue, progress_fun = None):
    total = len(queue)
    start = datetime.now()
    with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
        res = pool.imap_unordered(work_fun, queue)
        for i, data in enumerate(res, 1):
            if progress_fun:
                progress_fun(i, data)
            elapsed = datetime.now() - start
            eta = (total - i) / i * elapsed
            sys.stdout.write("\r\033[K Images updated: {0} | ETA: {1}".format(
                i, str(eta).split('.')[0]))
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

#-----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
