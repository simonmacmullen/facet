#!/usr/bin/env python3

import os
from optparse import OptionParser
import subprocess
import json
import sys

def main():
    parser = OptionParser(usage = "usage: %prog [options] src-images dest")
    (options, args) = parser.parse_args()
    if len(args) != 2:
        parser.print_help()
        exit(1)
    src = args[0]
    dest = args[1]
    build(src, dest)

def build(src, dest):
    print("\n Facet generator\n ---------------\n")
    os.makedirs(dest, exist_ok = True)
    files = find_images(src)
    db_path = os.path.join(dest, "db.json")
    build_db(files, db_path)
    scale_all_images(dest, files)

def build_db(files, db_path):
    db = load_db(db_path)
    todo = todo_images_in_db(files, db)
    print(" Database: [{0}] images to update of [{1}] total".format(
        len(todo), len(files)))
    update_images_in_db(todo, db)
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
            path = os.path.join(root, f)
            timestamp = os.path.getmtime(path)
            res.append((path, timestamp))
    return res

def todo_images_in_db(images, db):
    return [(f, t) for (f, t) in images
            if f not in db or db[f]['timestamp'] != t]

def update_images_in_db(images, db):
    ix = 0
    for (filename, timestamp) in images:
        db[filename] = parse_image(filename, timestamp)
        ix += 1
        sys.stdout.write("\r\033[K Database: image {0} ({1})".format(
            ix, filename))
        sys.stdout.flush()
    sys.stdout.write("\r\033[K")

def parse_image(path, timestamp):
    cmd = ["identify", "-format", "%[IPTC:2:25]\n%[width]\n%[height]", path]
    out = subprocess.check_output(cmd).decode('utf-8').splitlines()
    keywords = [k for k in out[0].split(';') if good_keyword(k)]
    width = int(out[1])
    height = int(out[2])
    return {'path':      path,
            'keywords':  keywords,
            'width':     width,
            'height':    height,
            'timestamp': timestamp}

def good_keyword(k):
    if k == '\\':
        return False
    return True

def scale_all_images(dest, files):
    scale_image_set(dest, files, "150")
    scale_image_set(dest, files, "1000")

def scale_image_set(dest, files, size):
    scaled = os.path.join(dest, "scaled", size)
    os.makedirs(scaled, exist_ok = True)
    todo = todo_scaled_images(scaled, files)
    print(" Images {0}: [{1}] images to scale of [{2}] total".format(
        size, len(todo), len(files)))
    scale_images(scaled, todo, size)
    print(" Images {0}: scaled\n".format(size))

def todo_scaled_images(scaled, images):
    return [(f, t) for (f, t) in images
            if todo_scaled_image(f, t, scaled)]

def todo_scaled_image(filename, timestamp, scaled):
    dest = os.path.join(scaled, filename)
    return not os.path.isfile(dest) or timestamp > os.path.getmtime(dest)

def scale_images(scaled, images, size):
    ix = 0
    for (filename, timestamp) in images:
        scale_image(scaled, filename, size)
        ix += 1
        sys.stdout.write("\r\033[K Images {0}: image {1} ({2})".format(
            size, ix, filename))
        sys.stdout.flush()
    sys.stdout.write("\r\033[K")

def scale_image(scaled, filename, size):
    dest = os.path.join(scaled, filename)
    os.makedirs(os.path.dirname(dest), exist_ok = True)
    cmd = ["convert", filename, "-auto-orient",
           "-thumbnail", "{0}x{1}".format(size, size), "-unsharp", "0x.5", dest]
    subprocess.check_call(cmd)

if __name__ == "__main__":
    main()
