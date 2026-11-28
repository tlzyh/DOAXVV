# -*- coding: utf-8 -*-
"""Parse the root archive directories (pkginfo) into out/archive_dir.csv.

Each quality folder has one root file whose name is hardcoded in the exe.
It starts with the u32 inflated size, followed by the usual page stream keyed
by key_from_index(size). The inflated KTGL block "pkginfo" holds a "btif"
table (parsed at 0x142edef20). Offsets in its header are relative to
btif + 0x28:

    +0x08 record count     +0x14 records     +0x18 names     +0x1c paths
    +0x20 alias count      +0x24 aliases (u32 key, u32 value)

Each 40-byte record is

    u32 key, u32 type, u32 name offset, u32 path offset, u32 flags,
    u32 plain size, u32 stored size, u32 a, u32 b, u32 c

The key is the resource id the game looks up (0x142edf0c0); release builds
leave every name empty. Paths are "FOLDER/<64 hex>".
"""
import argparse
import csv
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import decrypt as D  # noqa: E402

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
OUT = os.path.join(os.path.dirname(__file__), "..", "out")
ROOTS = {
    "COMMON": "4be7efcc93f64e14d7bd7984ef6eeb2ef5ad802ea74cf12ad50a4d39bab71798",
    "HIGH": "9b2d39b6d57f8613d9a316d8c3e6120886640a5762ea23c8fcc88d8acc7563b4",
    "LOW": "4e172f40859f78ae3b61db95d114f046e39211a356989a418f0069f66a24bb0d",
}
RECORD = struct.Struct("<10I")


def load_root(folder):
    path = os.path.join(ROOT, folder, ROOTS[folder])
    if not os.path.exists(path):
        return None
    data = open(path, "rb").read()
    total = struct.unpack_from("<I", data, 0)[0]
    return D.inflate_all(data[4:], D.key_from_index(total))


def ktgl_entries(buf, pos):
    """Entry offsets of the KTGL block at pos (name padded to 8 bytes)."""
    head = pos + 8
    count = struct.unpack_from("<I", buf, head + 0x10)[0]
    table = head + struct.unpack_from("<I", buf, head + 4)[0]
    return [pos + struct.unpack_from("<I", buf, table + 4 * i)[0] for i in range(count)]


def find_btif(buf):
    pos = buf.find(b"btif\0\0")
    if pos < 0:
        raise ValueError("no btif table")
    return pos


def _cstr(buf, pos):
    return buf[pos:buf.index(b"\0", pos)].decode("latin1")


def records(buf):
    bt = find_btif(buf)
    count, = struct.unpack_from("<I", buf, bt + 8)
    rec, names, paths = (bt + 0x28 + v for v in struct.unpack_from("<3I", buf, bt + 0x14))
    for i in range(count):
        key, kind, name, path, flags, plain, stored, a, b, c = RECORD.unpack_from(buf, rec + RECORD.size * i)
        yield dict(key=key, type=kind, name=_cstr(buf, names + name), path=_cstr(buf, paths + path),
                   flags=flags, plain=plain, stored=stored, a=a, b=b, c=c)


def aliases(buf):
    bt = find_btif(buf)
    count, off = struct.unpack_from("<2I", buf, bt + 0x20)
    return [struct.unpack_from("<2I", buf, bt + 0x28 + off + 8 * i) for i in range(count)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dump", action="store_true", help="also save inflated pkginfo to out/")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, "archive_dir.csv")
    total = 0
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["root", "key", "type", "name", "folder", "hash", "exists", "flags",
                    "plain", "stored", "a", "b", "c"])
        for root in ROOTS:
            buf = load_root(root)
            if buf is None:
                print(root, "missing")
                continue
            if args.dump:
                open(os.path.join(OUT, "_pkginfo_%s.bin" % root.lower()), "wb").write(buf)
            n = have = 0
            for r in records(buf):
                folder, _, h = r["path"].rpartition("/")
                exists = bool(h) and os.path.exists(os.path.join(ROOT, folder, h))
                w.writerow([root, "%08x" % r["key"], r["type"], r["name"], folder, h, int(exists),
                            "%08x" % r["flags"], r["plain"], r["stored"],
                            "%08x" % r["a"], "%08x" % r["b"], "%08x" % r["c"]])
                n += 1
                have += exists
            print(root, "records", n, "present", have, "aliases", len(aliases(buf)))
            total += n
    print("wrote", out, total)


if __name__ == "__main__":
    main()
