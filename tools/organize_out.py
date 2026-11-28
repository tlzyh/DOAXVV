# -*- coding: utf-8 -*-
"""Write the catalog tables that tie the game's chr_data to the exported glbs.

  python tools\\organize_out.py [--prune]

Also lists glbs under out\\models\\ that no TMC maps to any more (a game update
renamed or dropped them); --prune deletes them with their _tex folders.

out\\catalog\\ (paths relative to out\\, layout.py):
  models.csv          tmc_hash, name, out_name, category, group, dir_type, source,
                      tmcl_hash, pairing, glb, tex_dir, textures, meshes, materials,
                      glb_bytes
  characters.csv      chr_characters.csv (body_* renamed effect_*: chr_xxx is a glow
                      effect, the body is part of every costume) plus effect_glb, face_glb
  char_costumes.csv   char_costumes.py
  motion_sets.csv     copy of out\\chr_motion_sets.csv
  pairing.csv         written by export_gltf.py --all
  motions.csv         written by export_motion.py (one row per exported .vmot)
"""
import csv
import json
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import layout  # noqa: E402

JSON_CHUNK = 0x4E4F534A


def read_glb(path):
    with open(path, "rb") as fh:
        blob = fh.read()
    json_len = struct.unpack_from("<I", blob, 12)[0]
    return json.loads(blob[20:20 + json_len]), blob[20 + json_len:]


def read_glb_json(path):
    with open(path, "rb") as fh:
        head = fh.read(20)
        return json.loads(fh.read(struct.unpack_from("<I", head, 12)[0]))


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


def write_csv(name, header, rows):
    with open(os.path.join(layout.CATALOG, name), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print("wrote", name, len(rows))


def catalog():
    os.makedirs(layout.CATALOG, exist_ok=True)
    rows = [r for r in csv.DictReader(open(layout.INDEX, encoding="utf-8")) if r["magic"] == "TMC"]
    names = layout.out_names(rows)
    types = layout.directory_types()
    pairing_path = os.path.join(layout.CATALOG, "pairing.csv")
    pairing = {r["tmc_hash"]: r for r in csv.DictReader(open(pairing_path, encoding="utf-8"))} \
        if os.path.exists(pairing_path) else {}

    first = {}
    for row in sorted(rows, key=lambda r: os.path.isabs(r["folder"])):
        first.setdefault(row["hash"], row)
    models = []
    for row in sorted(first.values(), key=lambda r: names[r["hash"]]):
        h = row["hash"]
        category = layout.category_of(h, types)
        group = layout.group_of(row["name"])
        glb = layout.model_path(category, group, names[h])
        p = pairing.get(h, {})
        source = "cdn" if os.path.isabs(row["folder"]) else "game"
        info = ["", "", "", "", ""]
        if os.path.exists(glb):
            doc = read_glb_json(glb)
            tex_dir = layout.tex_dir(glb)
            info = [layout.rel(tex_dir) if os.path.isdir(tex_dir) else "", len(doc.get("images", [])),
                    len(doc.get("meshes", [])), len(doc.get("materials", [])), os.path.getsize(glb)]
        models.append([h, row["name"], names[h], category, group, types.get(h, ""), source, p.get("tmcl_hash", ""),
                       "official" if p.get("tmcl_matches") == "official" else ("guess" if p else ""),
                       layout.rel(glb) if os.path.exists(glb) else ""] + info)
    write_csv("models.csv", ("tmc_hash", "name", "out_name", "category", "group", "dir_type", "source", "tmcl_hash",
                             "pairing", "glb", "tex_dir", "textures", "meshes", "materials", "glb_bytes"), models)

    glb_of = {m[0]: m[9] for m in models}
    chars = list(csv.DictReader(open(os.path.join(layout.OUT, "chr_characters.csv"), encoding="utf-8")))
    header = [k.replace("body_", "effect_") for k in chars[0].keys()]
    write_csv("characters.csv", header + ["effect_glb", "face_glb"],
              [list(c.values()) + [glb_of.get(c["body_tmc"], ""), glb_of.get(c["face_tmc"], "")] for c in chars])

    import char_costumes
    char_costumes.write(glb_of)
    shutil.copyfile(os.path.join(layout.OUT, "chr_motion_sets.csv"), os.path.join(layout.CATALOG, "motion_sets.csv"))
    print("copied motion_sets.csv")
    for stale in ("textures.csv", "model_textures.csv"):
        path = os.path.join(layout.CATALOG, stale)
        if os.path.exists(path):
            os.remove(path)
            print("removed", stale)
    return {m[9] for m in models if m[9]}


def stale_glbs(current):
    """glbs under out\\models\\ that no TMC maps to any more (renamed or dropped by a game update)."""
    found = []
    for dirpath, _dirnames, filenames in os.walk(layout.MODELS):
        for f in filenames:
            if f.endswith(".glb") and not f.endswith("_anim.glb"):
                path = os.path.join(dirpath, f)
                if layout.rel(path) not in current:
                    found.append(path)
    return sorted(found)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prune", action="store_true", help="delete stale glbs and their _tex folders")
    args = ap.parse_args()
    stale = stale_glbs(catalog())
    print("stale glbs", len(stale))
    for path in stale[:20]:
        print(" ", layout.rel(path))
    if args.prune:
        for path in stale:
            os.remove(path)
            if os.path.isdir(layout.tex_dir(path)):
                shutil.rmtree(layout.tex_dir(path))
        for dirpath, _dirnames, _filenames in sorted(os.walk(layout.MODELS), key=lambda t: -len(t[0])):
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
        print("pruned", len(stale))


if __name__ == "__main__":
    main()
