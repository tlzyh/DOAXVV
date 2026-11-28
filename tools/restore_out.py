# -*- coding: utf-8 -*-
"""Move glbs from the old md5 store (out\\lib\\) back to per-model folders.

  python tools\\restore_out.py [--dry-run] [--limit N] [--workers 8] [--keep-lib]

For every out\\lib\\model\\<category>\\<name>.glb:
  - copies each texture out\\lib\\tex\\<aa>\\<md5>.png to <name>_tex\\NN.png, NN being
    images[].extras.tmcl_texture (the texture's order in the TMCL)
  - points the image uri at <name>_tex/NN.png and writes the glb to
    out\\models\\<category>\\<group>\\<name>.glb (layout.py)
Rerunnable: glbs already moved are gone from out\\lib\\. Once every glb under
out\\models\\ resolves all its textures, out\\lib\\ is deleted (unless --keep-lib)
and the catalog is rewritten (organize_out.py).
"""
import argparse
import concurrent.futures
import csv
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(__file__))
import layout  # noqa: E402
from organize_out import catalog, read_glb, write_glb  # noqa: E402

LIB = os.path.join(layout.OUT, "lib")
LIB_MODEL = os.path.join(LIB, "model")


def restore_one(path, by_name, names, types, dry_run):
    stem = os.path.splitext(os.path.basename(path))[0]
    tmc_hash = by_name.get(stem[:-5] if stem.endswith("_anim") else stem, "")
    dest = layout.model_path(layout.category_of(tmc_hash, types), layout.group_of(names.get(tmc_hash, stem)), stem)
    if dry_run:
        return dest, 0
    doc, rest = read_glb(path)
    tex_dir = layout.tex_dir(dest)
    missing = 0
    for i, image in enumerate(doc.get("images", [])):
        uri = image.get("uri", "")
        number = image.get("extras", {}).get("tmcl_texture", i)
        filename = "%02d.png" % number
        target = os.path.join(tex_dir, filename)
        if uri.startswith("../../tex/"):
            src = os.path.normpath(os.path.join(os.path.dirname(path), uri.replace("/", os.sep)))
            if os.path.exists(src):
                os.makedirs(tex_dir, exist_ok=True)
                shutil.copyfile(src, target)
                if os.path.exists(src[:-4] + ".dds"):
                    shutil.copyfile(src[:-4] + ".dds", target[:-4] + ".dds")
            else:
                missing += 1
        image["uri"] = os.path.basename(tex_dir) + "/" + filename
    write_glb(dest, doc, rest)
    os.remove(path)
    return dest, missing


def check_models():
    glbs, broken = 0, []
    for dirpath, _dirnames, filenames in os.walk(layout.MODELS):
        for f in filenames:
            if not f.endswith(".glb"):
                continue
            glbs += 1
            path = os.path.join(dirpath, f)
            doc, _rest = read_glb(path)
            for image in doc.get("images", []):
                if not os.path.exists(os.path.join(dirpath, image.get("uri", "").replace("/", os.sep))):
                    broken.append(path)
                    break
    return glbs, broken


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="only print where the glbs would go")
    ap.add_argument("--limit", type=int, default=0, help="restore only the first N glbs (trial run)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--keep-lib", action="store_true", help="do not delete out\\lib\\ afterwards")
    args = ap.parse_args()

    rows = [r for r in csv.DictReader(open(layout.INDEX, encoding="utf-8")) if r["magic"] == "TMC"]
    out_names = layout.out_names(rows)
    by_name = {name: h for h, name in out_names.items()}
    names = {r["hash"]: r["name"] for r in rows}
    types = layout.directory_types()
    glbs = sorted(os.path.join(dp, f) for dp, _dn, fn in os.walk(LIB_MODEL) for f in fn if f.endswith(".glb")) \
        if os.path.isdir(LIB_MODEL) else []
    if args.limit:
        glbs = glbs[:args.limit]
    print("glbs to restore", len(glbs), flush=True)
    missing = 0
    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        work = pool.map(lambda p: restore_one(p, by_name, names, types, args.dry_run), glbs)
        for n, (dest, m) in enumerate(work, 1):
            missing += m
            if args.dry_run and n <= 20:
                print(" ", layout.rel(dest))
            if n % 250 == 0:
                print("restored", n, "/", len(glbs), flush=True)
    print("restored", len(glbs), "missing textures", missing)
    if args.dry_run or args.limit:
        return

    count, broken = check_models()
    print("glbs in out\\models", count, "with missing textures", len(broken))
    for path in broken[:10]:
        print(" ", layout.rel(path))
    left = sum(1 for _dp, _dn, fn in os.walk(LIB_MODEL) for f in fn if f.endswith(".glb")) \
        if os.path.isdir(LIB_MODEL) else 0
    if os.path.isdir(LIB) and not args.keep_lib:
        if broken or left:
            print("keeping out\\lib (%d glbs left, %d broken)" % (left, len(broken)))
        else:
            shutil.rmtree(LIB)
            print("removed", LIB)
    catalog()


if __name__ == "__main__":
    main()
