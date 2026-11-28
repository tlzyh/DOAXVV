# -*- coding: utf-8 -*-
"""Match the draws of a RenderDoc dump (tools\\rdc_dump.py) to our exported models.

  python tools\\rdc_match.py out\\renderdoc\\misaki [--char 10] [--all-models]

1. Every primitive of the character's costumes, hairs and face (char_costumes.csv,
   characters.csv; --all-models: every glb in models.csv) is keyed by its index count.
   Draws with the same index count vote for their glb; the best glb of each category
   wins, and its draws are kept when every primitive's count is distinct enough.
2. For each draw with a matching index count, the textures the pixel shader reads
   (textures\\<id>.png) are compared with every candidate material's exported PNGs
   (size, then 128x128 mean difference < 0.01). The candidate matching the most registers wins;
   a draw is confirmed when it matched at least one texture and every tied candidate
   uses the same material. Confirmed
   draws give the TMC slot -> shader register (t0, t1 ...) mapping.
3. Every float4 of the draw's cbuffers is compared with the material's MtrCol rows.

Writes into the dump folder:
  matches.csv     glb candidates and their votes
  draws_matched.csv  event, glb, mesh, primitive, material, shaders, texture slot mapping
  slots.csv       per pixel shader: register -> TMC slot, with counts
  mtrcol.csv      cbuffer variable -> MtrCol row, with counts
"""
import argparse
import collections
import csv
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import layout  # noqa: E402
from organize_out import read_glb_json  # noqa: E402


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print("wrote %s %d" % (os.path.relpath(path, layout.OUT), len(rows)))


def candidates(char, all_models):
    """[(category, glb relative to out\\)]"""
    out = []
    if all_models:
        for row in read_csv(os.path.join(layout.CATALOG, "models.csv")):
            if row["glb"]:
                out.append((row["category"], row["glb"]))
        return out
    for row in read_csv(os.path.join(layout.CATALOG, "char_costumes.csv")):
        if row["char"] == str(char) and row["glb"]:
            out.append(("costume" if row["kind"] == "cos" else "hair", row["glb"]))
    for row in read_csv(os.path.join(layout.CATALOG, "characters.csv")):
        if row["row"] == str(char) and row["face_glb"]:
            out.append(("face", row["face_glb"]))
    return sorted(set(out))


def primitives(glb):
    doc = read_glb_json(os.path.join(layout.OUT, glb))
    accessors = doc["accessors"]
    out = []
    for mi, mesh in enumerate(doc.get("meshes", [])):
        for pi, prim in enumerate(mesh["primitives"]):
            if "indices" not in prim:
                continue
            out.append({"glb": glb, "mesh": mesh.get("name", str(mi)), "primitive": pi,
                        "material": prim.get("material", -1),
                        "indices": accessors[prim["indices"]]["count"],
                        "vertices": accessors[prim["attributes"]["POSITION"]]["count"],
                        "submesh": prim.get("extras", {}).get("submesh", -1)})
    return doc, out


def thumb(path):
    try:
        img = Image.open(path).convert("RGBA")
    except (OSError, ValueError):
        return None, None
    return img.size, np.asarray(img.resize((128, 128), Image.BILINEAR), dtype=np.float32) / 255.0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dump")
    ap.add_argument("--char", type=int, default=10)
    ap.add_argument("--all-models", action="store_true")
    args = ap.parse_args()
    dump = os.path.abspath(args.dump)

    actions = [r for r in read_csv(os.path.join(dump, "actions.csv")) if r["ps"] and r["indices"] != "0"]
    by_count = collections.defaultdict(list)
    for a in actions:
        by_count[int(a["indices"])].append(a)

    docs, prims_of = {}, {}
    votes = []
    for category, glb in candidates(args.char, args.all_models):
        try:
            doc, prims = primitives(glb)
        except (OSError, ValueError, KeyError):
            continue
        docs[glb], prims_of[glb] = doc, prims
        counts = {p["indices"] for p in prims}
        hit = {c for c in counts if c in by_count}
        if hit:
            votes.append({"category": category, "glb": glb, "primitives": len(prims), "distinct": len(counts),
                          "matched": len(hit), "ratio": round(len(hit) / len(counts), 3)})
    votes.sort(key=lambda v: (-v["ratio"], -v["matched"]))
    write_csv(os.path.join(dump, "matches.csv"), votes,
              ["category", "glb", "primitives", "distinct", "matched", "ratio"])

    best = {}
    for v in votes:
        if v["category"] not in best and v["ratio"] >= 0.5 and v["matched"] >= 2:
            best[v["category"]] = v
    for cat, v in best.items():
        print("best %-8s %s  %d / %d index counts" % (cat, v["glb"], v["matched"], v["distinct"]))
    if not best:
        print("no glb matches at least half of its index counts")

    thumbs = {}

    def texture_thumb(path):
        if path not in thumbs:
            thumbs[path] = thumb(path)
        return thumbs[path]

    def compare_textures(ps, extras, tex_dir):
        """[(register, slot, uv) or (register, None, None)] for the textures the pixel shader reads"""
        # extras.textures[].texture is the TMCL texture number = NN of <model>_tex\NN.png
        exported = [(t["slot"], t["uv"], os.path.join(tex_dir, "%02d.png" % t["texture"]))
                    for t in extras.get("textures", [])]
        out = []
        for bound in ps.get("textures", []):
            size, game = texture_thumb(os.path.join(dump, "textures", "%d.png" % bound["resource"]))
            if game is None:
                continue
            best_slot, best_diff = (None, None), 1.0
            for slot, uv, path in exported:
                esize, ours = texture_thumb(path)
                if ours is None or esize != size:
                    continue
                diff = float(np.abs(ours[..., :3] - game[..., :3]).mean())
                if diff < best_diff:
                    best_slot, best_diff = (slot, uv), diff
            out.append((bound["slot"],) + (best_slot if best_diff < 0.01 else (None, None)))
        return out

    def compare_mtrcol(draw, extras):
        mtr = [np.array(r, dtype=np.float32) for r in extras.get("mtrcol", []) if len(r) >= 4]
        found = []
        for stage_name, stage in draw["stages"].items():
            for cb in stage.get("cbuffers", []):
                for name, value in cb.get("values", {}).items():
                    vals = value if isinstance(value, list) else [value]
                    if vals and isinstance(vals[0], list):
                        continue
                    if len(vals) != 4 or not all(isinstance(x, float) for x in vals):
                        continue
                    vec = np.array(vals, dtype=np.float32)
                    if not np.any(vec):
                        continue
                    for k, row in enumerate(mtr):
                        if np.allclose(vec, row[:4], atol=1e-4):
                            found.append(("%s %s" % (stage_name, name), k))
        return found

    # every draw keeps the candidate primitive whose material textures match the most registers
    cands = collections.defaultdict(list)
    for v in best.values():
        for p in prims_of[v["glb"]]:
            for a in by_count.get(p["indices"], []):
                cands[a["event"]].append((a, p))

    rows = []
    slot_votes = collections.defaultdict(collections.Counter)
    mtr_votes = collections.defaultdict(collections.Counter)
    for event, options in cands.items():
        with open(os.path.join(dump, "draws", "%s.json" % event), encoding="utf-8") as fh:
            draw = json.load(fh)
        ps = draw["stages"].get("ps", {})
        scored = []
        for a, p in options:
            doc = docs[p["glb"]]
            material = doc["materials"][p["material"]] if p["material"] >= 0 else {}
            extras = material.get("extras", {})
            tex = compare_textures(ps, extras, layout.tex_dir(os.path.join(layout.OUT, p["glb"])))
            hits = sum(1 for t in tex if t[1] is not None)
            scored.append((hits, a, p, material, extras, tex))
        scored.sort(key=lambda s: -s[0])
        hits, a, p, material, extras, tex = scored[0]
        tied_materials = {(s[2]["glb"], s[2]["material"]) for s in scored if s[0] == hits}
        tied = sum(1 for s in scored if s[0] == hits)
        found = compare_mtrcol(draw, extras) if hits else []
        confirmed = bool(hits) and len(tied_materials) == 1
        if confirmed:
            for reg, slot, _uv in tex:
                if slot is not None:
                    slot_votes[ps["shader"]]["t%d=slot%d" % (reg, slot)] += 1
            for var, k in found:
                mtr_votes[var][k] += 1
        rows.append({"event": a["event"], "pass": a["pass"], "indices": p["indices"], "glb": p["glb"],
                     "mesh": p["mesh"], "primitive": p["primitive"], "submesh": p["submesh"],
                     "material": material.get("name", ""), "tmc_material": extras.get("tmc_material", ""),
                     "vs": a["vs"], "ps": a["ps"], "cull": a["cull"], "blend": a["blend"],
                     "textures": " ".join("t%d=%s" % (reg, "slot%d/uv%d" % (slot, uv) if slot is not None else "?")
                                          for reg, slot, uv in tex),
                     "mtrcol": " ".join("%s=%d" % (var.replace(" ", "."), k) for var, k in found),
                     "texture_hits": hits, "candidates": len(options), "tied": tied,
                     "confirmed": confirmed})
    rows.sort(key=lambda r: int(r["event"]))
    by_pass = collections.defaultdict(lambda: [0, 0, 0])
    for a in actions:
        by_pass[int(a["pass"])][0] += 1
    for r in rows:
        by_pass[int(r["pass"])][1] += 1
        by_pass[int(r["pass"])][2] += r["confirmed"]
    print("pass  draws  same-index-count  confirmed-by-texture")
    for k in sorted(by_pass):
        n, m, c = by_pass[k]
        if m:
            print("%4d %6d %8d %8d" % (k, n, m, c))
    write_csv(os.path.join(dump, "draws_matched.csv"), rows,
              ["event", "pass", "indices", "glb", "mesh", "primitive", "submesh", "material", "tmc_material",
               "vs", "ps", "cull", "blend", "textures", "mtrcol", "texture_hits", "candidates", "tied",
               "confirmed"])
    write_csv(os.path.join(dump, "slots.csv"), [
        {"ps": ps, "mapping": m, "draws": n} for ps, c in sorted(slot_votes.items()) for m, n in c.most_common()],
        ["ps", "mapping", "draws"])
    write_csv(os.path.join(dump, "mtrcol.csv"), [
        {"variable": var, "mtrcol_row": k, "draws": n} for var, c in sorted(mtr_votes.items())
        for k, n in c.most_common()], ["variable", "mtrcol_row", "draws"])


if __name__ == "__main__":
    main()
