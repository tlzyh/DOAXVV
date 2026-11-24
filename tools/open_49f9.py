# -*- coding: utf-8 -*-
"""Open 49f9 files by varying the last byte of 01 56 55 xx."""
import collections
import csv
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(__file__))
from decrypt import decrypt, magic_of

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
INDEX = r"D:\Projects\YangHui\DOAXVV\index.csv"


def promising(blob):
    try:
        zlib.decompress(blob)
        return True
    except zlib.error as exc:
        text = str(exc)
        return "incomplete" in text or "truncated" in text


def main():
    rows = []
    for row in csv.DictReader(open(INDEX, encoding="utf-8")):
        if row["magic"]:
            continue
        full = os.path.join(ROOT, row["folder"], row["hash"])
        head = open(full, "rb").read(6)
        if head[4:6] == bytes.fromhex("49f9"):
            rows.append((row, full))
    print("files", len(rows))
    magics = collections.Counter()
    lasts = collections.Counter()
    missed = 0
    for row, full in rows:
        data = open(full, "rb").read(min(int(row["size"]), 20000))
        found = None
        for last in range(256):
            key = bytes((0x01, 0x56, 0x55, last))
            short = decrypt(data[:40], key)
            if short[4] != 0x78 or not promising(short[4:]):
                continue
            plain = decrypt(data, key)
            try:
                inflated = zlib.decompress(plain[4:])
            except zlib.error:
                continue
            found = (key, inflated)
            break
        if not found:
            missed += 1
            continue
        key, inflated = found
        lasts[key[3]] += 1
        magics[magic_of(inflated)] += 1
    print("opened", len(rows) - missed, "missed", missed)
    print("magics", dict(magics))
    print("last bytes", [(f"{b:02x}", n) for b, n in lasts.most_common(12)])


if __name__ == "__main__":
    main()
