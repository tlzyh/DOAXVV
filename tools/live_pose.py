# -*- coding: utf-8 -*-
"""Find which motion the game plays for a pose card, by diffing memory, read-only.

  python tools\\live_pose.py snap A        (pose 1 selected in photo mode)
  python tools\\live_pose.py diff A B      (after switching to pose 2)
  python tools\\live_pose.py dumpval VALUE SPAN TAG   (raw bytes around a value)

snap records every u32 address in DOAX_VV.exe whose value is a pose card item id
(item master category 0xf045f) or a chr_data mot row id ((motion << 16) | char).
diff re-reads the addresses of snapshot A, saves snapshot B, and lists the
addresses whose value changed between two candidates of the same kind, i.e.
the old -> new pose card and old -> new motion row. Output goes to
out\\live_pose_<A>_<B>.txt. Opens the process with QUERY_INFORMATION | VM_READ.
"""
import collections
import csv
import ctypes
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import live_names as L  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")


def candidates():
    import archive_dir as A
    import strpack as S
    items = S.db_table(A.load_root("COMMON"), 4)
    texts = {}
    for r in csv.DictReader(open(os.path.join(OUT, "strpack.csv"), encoding="utf-8-sig")):
        if r["hash"].startswith("f252e94d"):
            texts[int(r["id"])] = r["text"]
    poses = {int(r[0]): texts.get(int(r[1]) & 0xFFFF, "") for r in items if int(r[2]) == 0xf045f}
    mots = {int(r["id"], 16) for r in csv.DictReader(open(os.path.join(OUT, "chr_motion_sets.csv")))}
    return poses, mots


def open_game():
    pid = L.find_pid()
    if pid is None:
        sys.exit("DOAX_VV.exe is not running")
    handle = L.k32.OpenProcess(0x0410, False, pid)
    if not handle:
        sys.exit("OpenProcess failed, error %d (run elevated)" % ctypes.get_last_error())
    return handle


def snap(handle, wanted):
    addrs, vals = [], []
    for base, size in L.regions(handle, 512 << 20):
        blob = L.read(handle, base, size)
        if not blob:
            continue
        words = np.frombuffer(blob, dtype="<u4", count=(len(blob) & ~3) // 4)
        hit = np.nonzero(np.isin(words, wanted))[0]
        addrs.append(base + hit.astype(np.uint64) * 4)
        vals.append(words[hit])
    return np.concatenate(addrs), np.concatenate(vals)


def reread(handle, addrs):
    out = np.full(len(addrs), 0xFFFFFFFF, dtype=np.uint32)
    for base, size in L.regions(handle, 512 << 20):
        lo, hi = np.searchsorted(addrs, [base, base + size])
        if lo == hi:
            continue
        blob = L.read(handle, base, size)
        if not blob:
            continue
        words = np.frombuffer(blob, dtype="<u4", count=(len(blob) & ~3) // 4)
        idx = ((addrs[lo:hi] - np.uint64(base)) // np.uint64(4)).astype(np.int64)
        ok = idx < len(words)
        out[lo:hi][ok] = words[idx[ok]]
    return out


def save(tag, addrs, vals):
    np.savez(os.path.join(OUT, "_live_pose_%s.npz" % tag), addrs=addrs, vals=vals)


def dumpval(value, span, tag):
    """Save +-span bytes around every address holding value to out\\_dump_<tag>.npz."""
    handle = open_game()
    try:
        addrs, _ = snap(handle, np.array([value], dtype=np.uint32))
        blobs = [L.read(handle, int(a) - span, 2 * span) or b"" for a in addrs]
    finally:
        L.k32.CloseHandle(handle)
    np.savez(os.path.join(OUT, "_dump_%s.npz" % tag), addrs=addrs,
             blobs=np.array([b.ljust(2 * span, b"\0") for b in blobs], dtype="S%d" % (2 * span)))
    print("dumped", len(addrs), "areas")


def main():
    cmd, tags = sys.argv[1], sys.argv[2:]
    if cmd == "dumpval":
        return dumpval(int(tags[0]), int(tags[1]), tags[2])
    if cmd == "text":
        handle = open_game()
        needles = [tags[0].encode(), tags[0].encode("utf-16le")]
        with open(os.path.join(OUT, "_live_text_%s.txt" % tags[0]), "w", encoding="utf-8") as fh:
            for base, size in L.regions(handle, 512 << 20):
                blob = L.read(handle, base, size)
                for needle in needles if blob else ():
                    start = blob.find(needle)
                    while start >= 0:
                        ctx = blob[max(0, start - 160):start + 160]
                        if needle[1:2] == b"\0":
                            ctx = ctx.decode("utf-16le", "replace")
                        else:
                            ctx = ctx.decode("latin-1")
                        fh.write("%#x %r\n" % (base + start, ctx))
                        start = blob.find(needle, start + 1)
        L.k32.CloseHandle(handle)
        return
    if cmd == "region":
        handle = open_game()
        target = int(tags[0], 16)
        for base, size in L.regions(handle, 4 << 30):
            if base <= target < base + size:
                blob = L.read(handle, base, size) or b""
                with open(os.path.join(OUT, "_region_%x.bin" % base), "wb") as fh:
                    fh.write(blob)
                print("region %#x size %#x saved %d" % (base, size, len(blob)))
        L.k32.CloseHandle(handle)
        return
    if cmd == "banks":
        h2k = {r["hash"]: int(r["key"], 16) for r in csv.DictReader(open(os.path.join(OUT, "archive_dir.csv"), encoding="utf-8"))}
        char = int(tags[1], 0)
        keys = set()
        for r in csv.DictReader(open(os.path.join(OUT, "chr_motion_sets.csv"))):
            if int(r["id"], 16) & 0xFFFF == char:
                keys.update(h2k[h] for h in r["banks"].split() if h in h2k)
        handle = open_game()
        try:
            _addrs, vals = snap(handle, np.array(sorted(keys), dtype=np.uint32))
        finally:
            L.k32.CloseHandle(handle)
        counts = collections.Counter(int(v) for v in vals)
        with open(os.path.join(OUT, "_live_banks_%s.csv" % tags[0]), "w", newline="") as fh:
            csv.writer(fh).writerows(sorted(("%08x" % k, n) for k, n in counts.items()))
        print("bank keys present", len(counts), "of", len(keys))
        return
    if cmd == "base":
        handle = open_game()
        info = L.MBI()
        L.k32.VirtualQueryEx(handle, ctypes.c_void_p(int(tags[0], 16)), ctypes.byref(info), ctypes.sizeof(info))
        L.k32.CloseHandle(handle)
        return print("allocation base %#x" % info.AllocationBase)
    poses, mots = candidates()
    wanted = np.array(sorted(set(poses) | mots), dtype=np.uint32)
    handle = open_game()
    try:
        if cmd == "snap":
            addrs, vals = snap(handle, wanted)
            save(tags[0], addrs, vals)
            print("snap", tags[0], len(addrs), "addresses")
            return
        old = np.load(os.path.join(OUT, "_live_pose_%s.npz" % tags[0]))
        now = reread(handle, old["addrs"])
        addrs, vals = snap(handle, wanted)
        save(tags[1], addrs, vals)
    finally:
        L.k32.CloseHandle(handle)

    def kind(v):
        return "pose" if v in poses else "mot" if v in mots else None

    changes = collections.Counter()
    for a, before, after in zip(old["addrs"], old["vals"], now):
        before, after = int(before), int(after)
        if before != after and kind(before) and kind(before) == kind(after):
            changes[(kind(before), before, after)] += 1
    path = os.path.join(OUT, "live_pose_%s_%s.txt" % tuple(tags))
    with open(path, "w", encoding="utf-8") as fh:
        for (k, before, after), n in changes.most_common():
            if k == "pose":
                line = "pose %d %s -> %d %s  x%d" % (before, poses[before], after, poses[after], n)
            else:
                line = "mot %08x (motion %d char %d) -> %08x (motion %d char %d)  x%d" % (
                    before, before >> 16, before & 0xFFFF, after, after >> 16, after & 0xFFFF, n)
            fh.write(line + "\n")
            print(line)
    print("changed", len(changes), "->", path)


if __name__ == "__main__":
    main()
