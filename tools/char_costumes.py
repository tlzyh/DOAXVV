# -*- coding: utf-8 -*-
"""Per-character costume / hair lists from the official chr_data tables.

  python tools\\char_costumes.py [--no-links]

The exporter files models under out\\models\\<group>\\ by the second name segment
(KAS_MIS_za_16_a -> KAS), so one character's costumes are scattered over many
folders. This reads out\\chr_data\\cos.csv and hair.csv (run chr_data.py first),
which list every costume each character can wear, and writes

  out\\char_costumes.csv     char, code, kind (cos/hair), id, number, tmc, tmcl,
                            tmc_name, local, glb
  out\\chars\\<code>\\        hardlinks to the exported costume .glb files (hair in
                            hair\\) plus junctions to their _tex folders (the .glb
                            references _tex\\NN.png)

local = no means the client has not downloaded that costume yet (DMM fetches
costume data on demand), so it cannot be exported.
"""
import argparse
import collections
import csv
import os
import re
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "out")
MODELS = os.path.join(OUT, "models")
INDEX = os.path.join(REPO, "index.csv")


def group_of(name):
    parts = name.split("_")
    if len(parts) > 1 and len(parts[1]) == 3 and parts[1].isalpha() and parts[1].isupper():
        return parts[1]
    if len(parts[0]) == 3 and parts[0].isalpha() and parts[0].isupper():
        return parts[0]
    return "misc"


def glb_paths(index):
    """Same naming as export_gltf: duplicate names get a __hash8 suffix in (name, folder, hash) order."""
    used = collections.Counter()
    paths = {}
    tmcs = [r for r in index.values() if r["magic"] == "TMC"]
    for row in sorted(tmcs, key=lambda r: (r["name"], r["folder"], r["hash"])):
        base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", row["name"]) or row["hash"][:16]
        used[base] += 1
        out_name = base if used[base] == 1 else "%s__%s" % (base, row["hash"][:8])
        paths[row["hash"]] = os.path.join(MODELS, group_of(row["name"]), out_name + ".glb")
    return paths


def link(src, dst):
    if os.path.exists(dst):
        return
    try:
        os.link(src, dst)
    except OSError:
        return
    tex = src[:-4] + "_tex"
    if os.path.isdir(tex) and not os.path.exists(dst[:-4] + "_tex"):
        subprocess.run(["cmd", "/c", "mklink", "/J", dst[:-4] + "_tex", tex],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-links", action="store_true")
    args = parser.parse_args()
    index = {r["hash"]: r for r in csv.DictReader(open(INDEX, encoding="utf-8"))}
    codes = {int(r["char_id"]): r["code"] or r["face_name"].split("_")[0].lower()
             for r in csv.DictReader(open(os.path.join(OUT, "chr_characters.csv")))}
    glbs = glb_paths(index)
    rows = []
    for kind, tmc_type in (("cos", "25"), ("hair", "17")):
        for r in csv.DictReader(open(os.path.join(OUT, "chr_data", kind + ".csv"))):
            ident = int(r["id"], 16)
            code = codes.get(ident & 0xFFFF)
            if not code:
                continue
            words = [r["w%d" % i] for i in range(1, 8)]
            tmc = next((w.rpartition("/")[2] for w in words if w.startswith(tmc_type + ":")), "")
            tmcl = next((w.rpartition("/")[2] for w in words if w.startswith(str(int(tmc_type) + 1) + ":")), "")
            local = tmc in index and tmcl in index
            glb = glbs.get(tmc, "") if local else ""
            rows.append((r["char"], code, kind, r["id"], ident >> 16, tmc, tmcl,
                         index[tmc]["name"] if tmc in index else "", "yes" if local else "no",
                         os.path.relpath(glb, OUT) if glb and os.path.exists(glb) else ""))
    with open(os.path.join(OUT, "char_costumes.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(("char", "code", "kind", "id", "number", "tmc", "tmcl", "tmc_name", "local", "glb"))
        w.writerows(rows)
    stats = collections.defaultdict(lambda: [set(), set(), set()])
    for row in rows:
        if row[9] and not args.no_links:
            folder = os.path.join(OUT, "chars", row[1], "" if row[2] == "cos" else "hair")
            os.makedirs(folder, exist_ok=True)
            link(os.path.join(OUT, row[9]), os.path.join(folder, os.path.basename(row[9])))
        if row[2] != "cos":
            continue
        s = stats[row[1]]
        s[0].add(row[5])
        if row[8] == "yes":
            s[1].add(row[5])
        if row[9]:
            s[2].add(row[5])
    print("code  costumes  local  exported")
    for code, (allc, loc, exp) in sorted(stats.items()):
        print("%-4s  %8d  %5d  %8d" % (code, len(allc), len(loc), len(exp)))
    print("rows", len(rows), "->", os.path.join(OUT, "char_costumes.csv"))


if __name__ == "__main__":
    main()
