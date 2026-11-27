# -*- coding: utf-8 -*-
"""Pair body / hand / breast motion files by their clip lengths into out\\motion_sets.csv.

  python tools\\pair_motion.py [--workers 4]

Needs out\\motions.csv from survey_motion.py. Each char_dat gets a signature:
the frame count of every clip of its first multi-bone bank. Files of different
bank kinds with the same signature are listed as one set.
"""
import argparse
import collections
import csv
import multiprocessing
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from export_gltf import INDEX, read_inflated
from motion import length, motions

SURVEY = r"D:\Projects\YangHui\DOAXVV\out\motions.csv"
OUT = r"D:\Projects\YangHui\DOAXVV\out\motion_sets.csv"
KINDS = {"MOT00_Hips": "body", "OPT_Hand_Left_Root": "hand", "OPT_Breast_Left_base": "breast",
         "OPT_Hips_Left_base": "hips"}


def signature(row):
    buf = read_inflated(row)
    for motion in motions(buf):
        if motion.name in KINDS:
            # every track of a clip has the same length, so one track is enough
            return row["hash"], KINDS[motion.name], tuple(length(clip[0]) for clip in motion.clips)
    return row["hash"], None, ()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    wanted = {r["hash"] for r in csv.DictReader(open(SURVEY, encoding="utf-8")) if r["name"] in KINDS}
    rows = [r for r in csv.DictReader(open(INDEX, encoding="utf-8")) if r["hash"] in wanted]
    with multiprocessing.Pool(args.workers) as pool:
        found = pool.map(signature, rows, chunksize=8)
    groups = collections.defaultdict(lambda: collections.defaultdict(list))
    for hash_, kind, sig in found:
        if kind:
            groups[sig][kind].append(hash_)
    kinds = sorted(set(KINDS.values()))
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["clip_frames"] + kinds)
        for sig, by_kind in sorted(groups.items(), key=lambda item: item[0]):
            writer.writerow([" ".join(map(str, sig))] + [" ".join(sorted(by_kind.get(k, []))) for k in kinds])
    shapes = collections.Counter(tuple(len(by_kind.get(k, [])) for k in kinds) for by_kind in groups.values())
    print("signatures", len(groups), "kinds", kinds)
    for shape, count in shapes.most_common(12):
        print(" ", dict(zip(kinds, shape)), count)


if __name__ == "__main__":
    main()
