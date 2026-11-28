# -*- coding: utf-8 -*-
"""Per-character costume / hair list from the official chr_data tables.

  python tools\\char_costumes.py

Reads out\\chr_data\\cos.csv and hair.csv (run chr_data.py first), which list every
costume and hairstyle each character can wear, and writes
out\\catalog\\char_costumes.csv with the columns

  char, code, kind (cos/hair), id, number, tmc, tmcl, tmc_name, local, glb

local = no means the files are neither in the game folders nor in cdn\\
(tools\\cdn_fetch.py downloads them). glb is relative to out\\ (layout.py).
organize_out.py --catalog runs this as part of the catalog.
"""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import layout  # noqa: E402


def write(glb_of=None):
    index = {r["hash"]: r for r in csv.DictReader(open(layout.INDEX, encoding="utf-8"))}
    if glb_of is None:
        tmcs = [r for r in index.values() if r["magic"] == "TMC"]
        types = layout.directory_types()
        glb_of = {}
        for h, name in layout.out_names(tmcs).items():
            path = layout.model_path(layout.category_of(h, types), name)
            glb_of[h] = layout.rel(path) if os.path.exists(path) else ""
    codes = {int(r["char_id"]): r["code"] or r["face_name"].split("_")[0].lower()
             for r in csv.DictReader(open(os.path.join(layout.OUT, "chr_characters.csv")))}
    rows = []
    for kind, tmc_type in (("cos", "25"), ("hair", "17")):
        for r in csv.DictReader(open(os.path.join(layout.OUT, "chr_data", kind + ".csv"))):
            ident = int(r["id"], 16)
            code = codes.get(ident & 0xFFFF)
            if not code:
                continue
            words = [r["w%d" % i] for i in range(1, 8)]
            tmc = next((w.rpartition("/")[2] for w in words if w.startswith(tmc_type + ":")), "")
            tmcl = next((w.rpartition("/")[2] for w in words if w.startswith(str(int(tmc_type) + 1) + ":")), "")
            local = tmc in index and tmcl in index
            rows.append((r["char"], code, kind, r["id"], ident >> 16, tmc, tmcl,
                         index[tmc]["name"] if tmc in index else "", "yes" if local else "no",
                         glb_of.get(tmc, "") if local else ""))
    os.makedirs(layout.CATALOG, exist_ok=True)
    with open(os.path.join(layout.CATALOG, "char_costumes.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(("char", "code", "kind", "id", "number", "tmc", "tmcl", "tmc_name", "local", "glb"))
        w.writerows(rows)
    stats = collections.defaultdict(lambda: [set(), set(), set()])
    for row in rows:
        if row[2] == "cos" and row[5]:
            s = stats[row[1]]
            s[0].add(row[5])
            if row[8] == "yes":
                s[1].add(row[5])
            if row[9]:
                s[2].add(row[5])
    print("code  costumes  local  exported")
    for code, (allc, loc, exp) in sorted(stats.items()):
        print("%-4s  %8d  %5d  %8d" % (code, len(allc), len(loc), len(exp)))
    print("wrote char_costumes.csv", len(rows))


if __name__ == "__main__":
    write()
