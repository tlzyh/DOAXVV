# -*- coding: utf-8 -*-
"""Retry known keys, then 4-byte keys, on files the index left blank."""
import collections
import csv
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(__file__))
from decrypt import SEED, decrypt, first_page, magic_of

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
INDEX = r"D:\Projects\YangHui\DOAXVV\index.csv"
KNOWN = [
    "0156553e", "02ae6d22", "076a612e", "961a", "0adb01", "016fc6",
    "0dbac4", "2b4f74", "8d452e", "092ff0", "d655", "01abfe",
]


def pair_of(key, plain5):
    out = bytearray()
    for i, value in enumerate((0x78, plain5)):
        index = 4 + i
        mixed = SEED[index % len(SEED)] ^ key[index % len(key)]
        if value == 0 or value == mixed:
            out.append(value)
        else:
            out.append(value ^ mixed)
    return bytes(out)


def main():
    wanted = {}
    for hexkey in KNOWN:
        key = bytes.fromhex(hexkey)
        for plain5 in (0x9C, 0xDA):
            wanted.setdefault(pair_of(key, plain5), []).append(key)
    rows = [row for row in csv.DictReader(open(INDEX, encoding="utf-8")) if not row["magic"]]
    groups = collections.defaultdict(list)
    hit = collections.Counter()
    for row in rows:
        full = os.path.join(ROOT, row["folder"], row["hash"])
        head = open(full, "rb").read(8)
        groups[head[4:6]].append((row, full, head))
    print("groups", len(groups))
    for pair, items in groups.items():
        keys = wanted.get(pair, [])
        if not keys:
            continue
        ok = 0
        for row, full, head in items:
            data = open(full, "rb").read(min(int(row["size"]), 20000))
            for key in keys:
                page = first_page(data, key)
                if page:
                    ok += 1
                    hit[magic_of(page)] += 1
                    break
        if ok:
            print(pair.hex(), "opened", ok, "of", len(items), "with", keys[0].hex())
    print("magics", dict(hit))


if __name__ == "__main__":
    main()
