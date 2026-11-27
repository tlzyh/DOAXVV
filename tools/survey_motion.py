# -*- coding: utf-8 -*-
"""List every motion block in every char_dat file into out\\motions.csv.

  python tools\\survey_motion.py [--workers 4]

Columns: hash, inflated size, motion number, first node name, node count, clip count.
Character banks are the rows with 21 nodes (MOT00_Hips .. MOT20_RightToe).
"""
import argparse
import csv
import multiprocessing
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from export_gltf import INDEX, read_inflated
from motion import motions

OUT = r"D:\Projects\YangHui\DOAXVV\out\motions.csv"


def survey(row):
    try:
        buf = read_inflated(row)
        found = [(number, m.name, m.node_count, len(m.clips)) for number, m in enumerate(motions(buf))]
    except Exception as exc:  # noqa: BLE001 - one bad file must not stop the survey
        return [(row["hash"], 0, -1, "error: %s" % exc, 0, 0)]
    return [(row["hash"], len(buf)) + item for item in found] or [(row["hash"], len(buf), -1, "", 0, 0)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    rows = [row for row in csv.DictReader(open(INDEX, encoding="utf-8")) if row["magic"] == "char_dat"]
    results = []
    with multiprocessing.Pool(args.workers) as pool:
        for done, items in enumerate(pool.imap_unordered(survey, rows), 1):
            results.extend(items)
            if done % 100 == 0:
                print("char_dat", done, "/", len(rows), flush=True)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("hash", "size", "motion", "name", "nodes", "clips"))
        writer.writerows(sorted(results))
    banks = [r for r in results if r[4] == 21]
    print("motions", sum(1 for r in results if r[2] >= 0), "character banks", len(banks),
          "clips", sum(r[5] for r in banks), "errors", sum(1 for r in results if str(r[3]).startswith("error")))


if __name__ == "__main__":
    main()
