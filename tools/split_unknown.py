# -*- coding: utf-8 -*-
"""Split still-locked files into the 4A 7B pool and other groups."""
import collections
import csv
import os

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
INDEX = r"D:\Projects\YangHui\DOAXVV\index.csv"


def main():
    rows = [row for row in csv.DictReader(open(INDEX, encoding="utf-8")) if not row["magic"]]
    print("unknown", len(rows))
    kinds = collections.Counter()
    pairs = collections.Counter()
    examples = {}
    for row in rows:
        full = os.path.join(ROOT, row["folder"], row["hash"])
        head = open(full, "rb").read(8)
        if head[4:6] == bytes((0x4A, 0x7B)) and head[2:4] == b"\x00\x00":
            kind = "4a7b"
        elif head.startswith(bytes.fromhex("3026b2758e66cf11")):
            kind = "asf"
        else:
            kind = "other"
            pairs[head[4:6]] += 1
            examples.setdefault(head[4:6], (row["folder"], row["hash"][:12], row["size"], head.hex()))
        kinds[kind] += 1
    print(dict(kinds))
    print("other distinct pairs", len(pairs))
    for pair, count in pairs.most_common(15):
        print(count, pair.hex(), examples[pair])


if __name__ == "__main__":
    main()
