# -*- coding: utf-8 -*-
import collections
import csv
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(__file__))
from decrypt import decrypt

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
INDEX = r"D:\Projects\YangHui\DOAXVV\index.csv"


def promising(blob):
    try:
        zlib.decompress(blob)
        return True
    except zlib.error as exc:
        text = str(exc)
        return "incomplete" in text or "truncated" in text


def opens(data, key):
    short = decrypt(data[:48], key)
    if short[4] != 0x78 or not promising(short[4:]):
        return False
    try:
        zlib.decompress(decrypt(data, key)[4:])
        return True
    except zlib.error:
        return False


def main():
    rows = []
    for row in csv.DictReader(open(INDEX, encoding="utf-8")):
        if row["magic"]:
            continue
        full = os.path.join(ROOT, row["folder"], row["hash"])
        head = open(full, "rb").read(8)
        rows.append((row, full, head))
    missed = []
    f29c = []
    for row, full, head in rows:
        if head[4:6] == bytes.fromhex("49f9"):
            data = open(full, "rb").read(min(int(row["size"]), 12000))
            if not any(opens(data, bytes((0x01, 0x56, 0x55, last))) for last in range(256)):
                missed.append((row["hash"][:16], row["size"], head.hex()))
        elif head[4:6] == bytes.fromhex("f29c"):
            f29c.append(int(row["size"]))
    print("49f9 still closed", len(missed))
    for item in missed[:8]:
        print(" ", item)
    print("f29c", len(f29c), "min", min(f29c), "mid", sorted(f29c)[len(f29c)//2], "max", max(f29c))


if __name__ == "__main__":
    main()
