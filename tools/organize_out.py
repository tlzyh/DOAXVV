# -*- coding: utf-8 -*-
"""Move exported models into the shared layout and write the catalog tables.

  python tools\\organize_out.py [--limit N] [--workers 8]   migrate, then --catalog
  python tools\\organize_out.py --catalog                   only rewrite out\\catalog\\

Migration (rerunnable, skips what is done):
  - removes out\\chars\\ (hardlinks and _tex junctions; junction targets are kept)
  - for every glb under out\\models\\: moves each texture into out\\lib\\tex\\ by md5
    (dropping duplicates), points the image uri there, records the original
    TMCL texture index in images[].extras.tmcl_texture, and moves the glb to
    out\\lib\\model\\<category>\\ (layout.py)
  - moves out\\models\\pairing.csv to out\\catalog\\ and removes emptied folders

Catalog (out\\catalog\\, paths relative to out\\):
  models.csv           tmc_hash, name, out_name, category, dir_type, source, tmcl_hash,
                       pairing, glb, meshes, materials, textures, glb_bytes,
                       geometry_md5, same_geometry_as
  model_textures.csv   tmc_hash, material, material_name, tmc_material, slot, uv,
                       tmcl_texture, tex_md5, tex
  textures.csv         md5, width, height, bytes, tex, models
  characters.csv       chr_characters.csv plus body_glb, face_glb
  char_costumes.csv    char_costumes.py
  motion_sets.csv      copy of out\\chr_motion_sets.csv
"""
import argparse
import collections
import concurrent.futures
import csv
import hashlib
import json
import os
import shutil
import stat
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import layout  # noqa: E402

OLD_MODELS = os.path.join(layout.OUT, "models")
OLD_CHARS = os.path.join(layout.OUT, "chars")
JSON_CHUNK = 0x4E4F534A


def read_glb(path):
    with open(path, "rb") as fh:
        blob = fh.read()
    json_len = struct.unpack_from("<I", blob, 12)[0]
    return json.loads(blob[20:20 + json_len]), blob[20 + json_len:]


def write_glb(path, doc, rest):
    text = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    text += b" " * (-len(text) % 4)
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, "wb") as fh:
        fh.write(struct.pack("<4sII", b"glTF", 2, 20 + len(text) + len(rest)))
        fh.write(struct.pack("<II", len(text), JSON_CHUNK))
        fh.write(text)
        fh.write(rest)
    os.replace(tmp, path)


def bin_md5(rest):
    return hashlib.md5(rest[8:]).hexdigest() if len(rest) >= 8 else ""


def is_junction(path):
    try:
        return bool(os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


def remove_chars():
    if not os.path.isdir(OLD_CHARS):
        return
    for dirpath, dirnames, filenames in os.walk(OLD_CHARS, topdown=True):
        for d in list(dirnames):
            full = os.path.join(dirpath, d)
            if is_junction(full):
                os.rmdir(full)
                dirnames.remove(d)
        for f in filenames:
            os.remove(os.path.join(dirpath, f))
    for dirpath, _dirnames, _filenames in sorted(os.walk(OLD_CHARS), key=lambda t: -len(t[0])):
        os.rmdir(dirpath)
    print("removed", OLD_CHARS)


def tmc_rows():
    return [r for r in csv.DictReader(open(layout.INDEX, encoding="utf-8")) if r["magic"] == "TMC"]


def migrate_one(path, by_name, types):
    stem = os.path.splitext(os.path.basename(path))[0]
    tmc_hash = by_name.get(stem[:-5] if stem.endswith("_anim") else stem, "")
    dest = layout.model_path(layout.category_of(tmc_hash, types), stem)
    doc, rest = read_glb(path)
    missing = 0
    for image in doc.get("images", []):
        uri = image.get("uri", "")
        if uri.startswith("../../tex/"):
            continue
        src = os.path.join(os.path.dirname(path), uri.replace("/", os.sep))
        number = os.path.splitext(os.path.basename(uri))[0]
        if not os.path.exists(src):
            missing += 1
            continue
        image["uri"] = layout.tex_uri(layout.store_texture(src))
        if number.isdigit():
            image.setdefault("extras", {})["tmcl_texture"] = int(number)
    write_glb(dest, doc, rest)
    if os.path.abspath(dest) != os.path.abspath(path):
        os.remove(path)
    return missing


def migrate(limit, workers):
    remove_chars()
    if not os.path.isdir(OLD_MODELS):
        return
    rows = tmc_rows()
    by_name = {name: h for h, name in layout.out_names(rows).items()}
    types = layout.directory_types()
    glbs = sorted(os.path.join(dp, f) for dp, _dn, fn in os.walk(OLD_MODELS) for f in fn if f.endswith(".glb"))
    if limit:
        glbs = glbs[:limit]
    print("glbs to move", len(glbs), flush=True)
    missing = 0
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        for n, m in enumerate(pool.map(lambda p: migrate_one(p, by_name, types), glbs), 1):
            missing += m
            if n % 250 == 0:
                print("moved", n, "/", len(glbs), flush=True)
    print("moved", len(glbs), "missing textures", missing)
    if limit:
        return
    os.makedirs(layout.CATALOG, exist_ok=True)
    old_log = os.path.join(OLD_MODELS, "pairing.csv")
    if os.path.exists(old_log):
        os.replace(old_log, os.path.join(layout.CATALOG, "pairing.csv"))
    for dirpath, _dirnames, _filenames in sorted(os.walk(OLD_MODELS), key=lambda t: -len(t[0])):
        if not os.listdir(dirpath):
            os.rmdir(dirpath)
    old_costumes = os.path.join(layout.OUT, "char_costumes.csv")
    if os.path.exists(old_costumes):
        os.remove(old_costumes)
    if os.path.isdir(OLD_MODELS):
        print("left in", OLD_MODELS, sum(len(fn) for _dp, _dn, fn in os.walk(OLD_MODELS)), "files")


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(24)
    return struct.unpack(">II", head[16:24]) if head[12:16] == b"IHDR" else (0, 0)


def write_csv(name, header, rows):
    with open(os.path.join(layout.CATALOG, name), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print("wrote", name, len(rows))


def catalog():
    os.makedirs(layout.CATALOG, exist_ok=True)
    rows = tmc_rows()
    names = layout.out_names(rows)
    types = layout.directory_types()
    pairing_path = os.path.join(layout.CATALOG, "pairing.csv")
    pairing = {r["tmc_hash"]: r for r in csv.DictReader(open(pairing_path, encoding="utf-8"))} \
        if os.path.exists(pairing_path) else {}

    models, model_tex, refs, first_geometry = [], [], collections.Counter(), {}
    for row in sorted(rows, key=lambda r: names[r["hash"]]):
        h = row["hash"]
        category = layout.category_of(h, types)
        glb = layout.model_path(category, names[h])
        p = pairing.get(h, {})
        source = "cdn" if os.path.isabs(row["folder"]) else "game"
        info = ["", "", "", "", "", ""]
        if os.path.exists(glb):
            doc, rest = read_glb(glb)
            geometry = bin_md5(rest)
            first_geometry.setdefault(geometry, h)
            image_md5 = {}
            for image in doc.get("images", []):
                md5 = os.path.splitext(os.path.basename(image.get("uri", "")))[0]
                image_md5[image.get("extras", {}).get("tmcl_texture")] = md5
            for md5 in set(image_md5.values()):
                refs[md5] += 1
            for m, material in enumerate(doc.get("materials", [])):
                extras = material.get("extras", {})
                for t in extras.get("textures", []):
                    md5 = image_md5.get(t.get("texture"), "")
                    model_tex.append((h, m, material.get("name", ""), extras.get("tmc_material", ""), t.get("slot"),
                                      t.get("uv"), t.get("texture"), md5,
                                      layout.rel(layout.tex_path(md5)) if md5 else ""))
            info = [len(doc.get("meshes", [])), len(doc.get("materials", [])), len(doc.get("images", [])),
                    os.path.getsize(glb), geometry, first_geometry[geometry] if first_geometry[geometry] != h else ""]
        models.append([h, row["name"], names[h], category, types.get(h, ""), source, p.get("tmcl_hash", ""),
                       "official" if p.get("tmcl_matches") == "official" else ("guess" if p else ""),
                       layout.rel(glb) if os.path.exists(glb) else ""] + info)
    write_csv("models.csv", ("tmc_hash", "name", "out_name", "category", "dir_type", "source", "tmcl_hash",
                             "pairing", "glb", "meshes", "materials", "textures", "glb_bytes",
                             "geometry_md5", "same_geometry_as"), models)
    write_csv("model_textures.csv", ("tmc_hash", "material", "material_name", "tmc_material", "slot", "uv",
                                     "tmcl_texture", "tex_md5", "tex"), model_tex)

    textures = []
    for dirpath, _dirnames, filenames in os.walk(layout.TEX):
        for f in filenames:
            if f.endswith(".png") and not f.startswith("_tmp_"):
                full = os.path.join(dirpath, f)
                md5 = f[:-4]
                w, hgt = png_size(full)
                textures.append((md5, w, hgt, os.path.getsize(full), layout.rel(full), refs.get(md5, 0)))
    write_csv("textures.csv", ("md5", "width", "height", "bytes", "tex", "models"), sorted(textures))

    glb_of = {m[0]: m[8] for m in models}
    chars = list(csv.DictReader(open(os.path.join(layout.OUT, "chr_characters.csv"), encoding="utf-8")))
    write_csv("characters.csv", list(chars[0].keys()) + ["body_glb", "face_glb"],
              [list(c.values()) + [glb_of.get(c["body_tmc"], ""), glb_of.get(c["face_tmc"], "")] for c in chars])

    import char_costumes
    char_costumes.write(glb_of)
    shutil.copyfile(os.path.join(layout.OUT, "chr_motion_sets.csv"), os.path.join(layout.CATALOG, "motion_sets.csv"))
    print("copied motion_sets.csv")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--catalog", action="store_true", help="only rewrite out\\catalog\\")
    ap.add_argument("--limit", type=int, default=0, help="migrate only the first N glbs (trial run)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if not args.catalog:
        migrate(args.limit, args.workers)
        if args.limit:
            return
    catalog()


if __name__ == "__main__":
    main()
