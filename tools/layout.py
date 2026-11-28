# -*- coding: utf-8 -*-
"""Output layout shared by export_gltf, restore_out, organize_out and char_costumes.

Mirrors how the game stores models: one TMC (meshes, materials, skeleton) plus
its own TMCL (textures, vertices, indices) per part, parts typed by the archive
directory (25 costume = body + swimsuit, 17 hair, 19 face, 53 accessory, ...),
and characters tied to parts only through the chr_data tables.

  out\\models\\<category>\\<group>\\<name>.glb       one glb per TMC
  out\\models\\<category>\\<group>\\<name>_tex\\NN.png  its textures, NN = TMCL order
  out\\catalog\\*.csv                               relations (chr_data -> glb)
"""
import collections
import csv
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "out")
MODELS = os.path.join(OUT, "models")
CATALOG = os.path.join(OUT, "catalog")
INDEX = os.path.join(REPO, "index.csv")

CATEGORY = {"25": "costume", "17": "hair", "19": "face", "39": "effect", "53": "accessory",
            "80": "prop", "27": "stage"}


def directory_types():
    """hash -> archive directory type."""
    return {r["hash"]: r["type"] for r in csv.DictReader(open(os.path.join(OUT, "archive_dir.csv"), encoding="utf-8"))}


def category_of(tmc_hash, types):
    return CATEGORY.get(types.get(tmc_hash, ""), "misc")


def safe_name(name, tmc_hash):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name) or tmc_hash[:16]


def group_of(name):
    """KAS_MIS_za_16_a -> MIS, MIS_hair_00 -> MIS, spfn_chair -> spfn."""
    parts = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).split("_")
    if len(parts) > 1 and re.fullmatch(r"[A-Z]{3}", parts[1]):
        return parts[1]
    return parts[0] or "misc"


def out_names(tmc_rows):
    """TMC hash -> output name: duplicate names get __hash8, in (name, cdn last, folder, hash) order.

    A hash present both in the game folders and in cdn\\ is named once, by its game copy.
    """
    used = collections.Counter()
    names = {}
    for row in sorted(tmc_rows, key=lambda r: (r["name"], os.path.isabs(r["folder"]), r["folder"], r["hash"])):
        if row["hash"] in names:
            continue
        base = safe_name(row["name"], row["hash"])
        used[base] += 1
        names[row["hash"]] = base if used[base] == 1 else "%s__%s" % (base, row["hash"][:8])
    return names


def model_path(category, group, out_name):
    return os.path.join(MODELS, category, group, out_name + ".glb")


def tex_dir(glb_path):
    return os.path.splitext(glb_path)[0] + "_tex"


def rel(path):
    return os.path.relpath(path, OUT).replace("\\", "/")
