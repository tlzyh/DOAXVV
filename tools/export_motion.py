# -*- coding: utf-8 -*-
"""Export char_dat motions to out\\motions\\<hash>.vmot for the viewer.

  python tools\\export_motion.py [--all | --sets | --char mis ...] [--hash 1e65b30a ...] [--workers N]

  --sets      every char_dat listed in out\\chr_motion_sets.csv (the game's mot table)
  --char      only the mot rows of these characters
  --all       every char_dat in index.csv
Writes out\\catalog\\motions.csv (hash, kinds, banks, clips, frames, bytes, file).

.vmot layout (little endian):
  "VMOT" u32 version (1) u32 bank count
  per bank:
    str root name, u8 kind (0 other, 1 body, 2 hand, 3 face, 4 breast, 5 root)
    u32 node count, node count x str bone name ("" if no reference model has it)
    node count x i32 parent, u32 clip count, clip count x u64 clip offset (from file start)
  per clip (at its offset):
    u32 samples (frames + 1), node count x 9 u8 flags (0 constant, 1 per sample)
    then for every node, for its 9 channels (translate xyz, rotate xyz radians
    applied x then y then z with row vectors, scale xyz): one f32 if constant,
    else samples x f32
  str = u16 byte length + utf-8
Bone names come from reference models: the subtree under the TMC node named like
the bank root, sorted by lower-cased name (see 阶段总结.md 10.2).
"""
import argparse
import csv
import multiprocessing
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import layout  # noqa: E402
from export_gltf import motion_targets, read_inflated  # noqa: E402
from motion import motions  # noqa: E402
from tmc import Tmc  # noqa: E402

MOTIONS = os.path.join(layout.OUT, "motions")
REFERENCE_NAMES = ("KAS_MIS_za_16_a", "*S_face_test_00")
KINDS = {"MOT00_Hips": 1, "OPT_Hand": 2, "OPT_Face": 3, "OPT_Breast": 4}
KIND_NAMES = ("other", "body", "hand", "face", "breast", "root")
REFERENCES = []


def kind_of(name):
    if name == "MOT00":
        return 5
    return next((k for prefix, k in KINDS.items() if name.startswith(prefix)), 0)


def bone_names(motion):
    for tmc in REFERENCES:
        targets = motion_targets(tmc, motion)
        if targets:
            return [tmc.nodes[targets[i]].name for i in range(motion.node_count)]
    return [""] * motion.node_count


def text(value):
    data = value.encode("utf-8")
    return struct.pack("<H", len(data)) + data


def encode_clip(motion, clip):
    samples = motion.clip_frames(clip) + 1
    channels = motion.channels(np.arange(samples), clip).astype(np.float32)
    flat = channels.reshape(samples, -1)
    animated = np.any(flat != flat[:1], axis=0)
    out = [struct.pack("<I", samples), animated.astype(np.uint8).tobytes()]
    for c in range(flat.shape[1]):
        out.append(flat[:, c].tobytes() if animated[c] else flat[0, c].tobytes())
    return b"".join(out), samples - 1


def export_file(row):
    path = os.path.join(MOTIONS, row["hash"] + ".vmot")
    try:
        banks = list(motions(read_inflated(row)))
    except Exception as exc:  # noqa: BLE001 - one bad file must not stop the export
        return row["hash"], "error: %s" % exc, "", 0, 0, 0, 0
    heads, bodies, clip_counts, frames = [], [], [], 0
    for motion in banks:
        clips = [encode_clip(motion, c) for c in range(len(motion.clips))]
        frames += sum(f for _data, f in clips)
        clip_counts.append(len(clips))
        head = text(motion.name) + struct.pack("<BI", kind_of(motion.name), motion.node_count)
        head += b"".join(text(n) for n in bone_names(motion))
        head += struct.pack("<%di" % motion.node_count, *motion.parents) + struct.pack("<I", len(clips))
        heads.append(head)
        bodies.append([data for data, _f in clips])
    position = 12 + sum(len(h) + 8 * n for h, n in zip(heads, clip_counts))
    table = []
    for clips in bodies:
        offsets = []
        for data in clips:
            offsets.append(position)
            position += len(data)
        table.append(struct.pack("<%dQ" % len(offsets), *offsets))
    blob = b"VMOT" + struct.pack("<II", 1, len(banks))
    blob += b"".join(h + t for h, t in zip(heads, table)) + b"".join(d for clips in bodies for d in clips)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(blob)
    os.replace(tmp, path)
    kinds = " ".join(KIND_NAMES[kind_of(m.name)] for m in banks)
    return row["hash"], "ok", kinds, len(banks), sum(clip_counts), frames, len(blob)


def init_worker(reference_rows):
    REFERENCES.extend(Tmc(read_inflated(r)) for r in reference_rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--sets", action="store_true", help="every char_dat in the game's mot table")
    ap.add_argument("--char", action="append", default=[], help="character code or id (repeatable)")
    ap.add_argument("--hash", action="append", default=[], help="char_dat hash prefix (repeatable)")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()

    index = [r for r in csv.DictReader(open(layout.INDEX, encoding="utf-8"))]
    by_hash = {}
    for r in sorted(index, key=lambda r: os.path.isabs(r["folder"])):
        if r["magic"] == "char_dat":
            by_hash.setdefault(r["hash"], r)
    wanted = set()
    if args.all:
        wanted = set(by_hash)
    if args.sets or args.char:
        ids = {int(r["char_id"]) for r in csv.DictReader(open(os.path.join(layout.OUT, "chr_characters.csv")))
               if not args.char or r["code"] in args.char or r["char_id"] in args.char}
        for r in csv.DictReader(open(os.path.join(layout.OUT, "chr_motion_sets.csv"), encoding="utf-8")):
            if int(r["id"], 16) & 0xFFFF in ids:
                wanted.update(r["banks"].split())
    if args.hash:
        wanted |= {h for h in by_hash if any(h.startswith(p) for p in args.hash)}
    rows = [by_hash[h] for h in sorted(wanted) if h in by_hash]
    if args.skip_existing:
        rows = [r for r in rows if not os.path.exists(os.path.join(MOTIONS, r["hash"] + ".vmot"))]
    if not rows:
        ap.error("nothing to export (give --all, --sets, --char or --hash)")
    names = {r["name"]: r for r in index if r["magic"] == "TMC" and not os.path.isabs(r["folder"])}
    reference_rows = [names[n] for n in REFERENCE_NAMES if n in names]
    os.makedirs(MOTIONS, exist_ok=True)
    print("char_dat files", len(rows), flush=True)

    results = []
    if args.workers == 1 or len(rows) == 1:
        init_worker(reference_rows)
        results = [export_file(r) for r in rows]
    else:
        with multiprocessing.Pool(args.workers, initializer=init_worker, initargs=(reference_rows,)) as pool:
            for n, result in enumerate(pool.imap_unordered(export_file, rows), 1):
                results.append(result)
                if n % 50 == 0:
                    print("files", n, "/", len(rows), flush=True)
    write_catalog(results)
    errors = [r for r in results if r[1] != "ok"]
    print("exported", len(results) - len(errors), "errors", len(errors),
          "MB %.1f" % (sum(r[6] for r in results if r[1] == "ok") / 1e6))
    for r in errors[:10]:
        print(" ", r[0][:16], r[1])


def write_catalog(results):
    """Merge into out\\catalog\\motions.csv, keyed by hash."""
    path = os.path.join(layout.CATALOG, "motions.csv")
    rows = {}
    if os.path.exists(path):
        rows = {r["hash"]: r for r in csv.DictReader(open(path, encoding="utf-8-sig"))}
    for r in results:
        if r[1] == "ok":
            rows[r[0]] = {"hash": r[0], "kinds": r[2], "banks": r[3], "clips": r[4], "frames": r[5],
                          "bytes": r[6], "file": "motions/%s.vmot" % r[0]}
    os.makedirs(layout.CATALOG, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, ("hash", "kinds", "banks", "clips", "frames", "bytes", "file"))
        w.writeheader()
        w.writerows(rows[h] for h in sorted(rows))


if __name__ == "__main__":
    main()
