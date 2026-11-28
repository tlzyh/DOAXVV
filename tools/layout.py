# -*- coding: utf-8 -*-
"""Output layout shared by export_gltf, organize_out and char_costumes.

  out\\lib\\model\\<category>\\<name>.glb   one glb per TMC (category from the
                                         TMC's archive directory type)
  out\\lib\\tex\\<aa>\\<md5>.png           every texture once, named by the md5 of
                                         its PNG bytes; glbs reference it as
                                         ../../tex/<aa>/<md5>.png
  out\\catalog\\*.csv                     relations for tools and viewers
"""
import collections
import csv
import hashlib
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "out")
LIB = os.path.join(OUT, "lib")
MODEL = os.path.join(LIB, "model")
TEX = os.path.join(LIB, "tex")
CATALOG = os.path.join(OUT, "catalog")
INDEX = os.path.join(REPO, "index.csv")

CATEGORY = {"25": "costume", "17": "hair", "19": "face", "39": "body", "53": "accessory",
            "80": "prop", "27": "stage"}


def directory_types():
    """hash -> archive directory type."""
    return {r["hash"]: r["type"] for r in csv.DictReader(open(os.path.join(OUT, "archive_dir.csv"), encoding="utf-8"))}


def category_of(tmc_hash, types):
    return CATEGORY.get(types.get(tmc_hash, ""), "misc")


def safe_name(name, tmc_hash):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name) or tmc_hash[:16]


def out_names(tmc_rows):
    """TMC hash -> output name: duplicate names get __hash8, in (name, cdn last, folder, hash) order."""
    used = collections.Counter()
    names = {}
    for row in sorted(tmc_rows, key=lambda r: (r["name"], os.path.isabs(r["folder"]), r["folder"], r["hash"])):
        base = safe_name(row["name"], row["hash"])
        used[base] += 1
        names[row["hash"]] = base if used[base] == 1 else "%s__%s" % (base, row["hash"][:8])
    return names


def model_path(category, out_name):
    return os.path.join(MODEL, category, out_name + ".glb")


def tex_path(md5):
    return os.path.join(TEX, md5[:2], md5 + ".png")


def tex_uri(md5):
    """Relative to a glb in lib\\model\\<category>\\."""
    return "../../tex/%s/%s.png" % (md5[:2], md5)


def md5_of_file(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def store_texture(src):
    """Move a PNG into the texture store (dropping it if an equal one is there); return its md5."""
    md5 = md5_of_file(src)
    dest = tex_path(md5)
    if os.path.exists(dest):
        os.remove(src)
    else:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            os.replace(src, dest)
        except OSError:
            if not os.path.exists(dest):
                raise
            os.remove(src)
    return md5


def rel(path):
    return os.path.relpath(path, OUT).replace("\\", "/")
