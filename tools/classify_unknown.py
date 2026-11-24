# -*- coding: utf-8 -*-
"""Classify locked files by plaintext header, not by a failed decrypt."""
import collections
import csv
import os

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
INDEX = r"D:\Projects\YangHui\DOAXVV\index.csv"


def label(head, size):
    if head[4:6] == bytes((0x4A, 0x7B)) and head[2:4] == b"\x00\x00":
        return "pool-4a7b"
    if head.startswith(bytes.fromhex("3026b2758e66cf11")):
        return "asf"
    if head[:4] == b"_L1G" or head[4:8] == b"0000" and head[:4] == b"_L1G":
        return "l1g"
    text = head[:8]
    if text[:4].startswith(b"_L1G") or text.startswith(b"_L1G"):
        return "l1g"
    if all(32 <= b < 127 or b == 0 for b in text[:8]) and any(65 <= b <= 90 or 97 <= b <= 122 for b in text[:4]):
        return "ascii:" + text.split(b"\x00", 1)[0][:8].decode("ascii", "replace")
    if head[:8] == b"\x00" * 8:
        return "zeros"
    if head[4:6] == bytes.fromhex("49f9"):
        return "pair-49f9"
    zeros = head.count(0)
    if zeros >= 6:
        return "sparse"
    return "opaque"


def main():
    rows = [row for row in csv.DictReader(open(INDEX, encoding="utf-8")) if not row["magic"]]
    kinds = collections.Counter()
    samples = {}
    for row in rows:
        full = os.path.join(ROOT, row["folder"], row["hash"])
        head = open(full, "rb").read(16)
        kind = label(head, int(row["size"]))
        kinds[kind] += 1
        samples.setdefault(kind, (row["folder"], int(row["size"]), head.hex()))
    for kind, count in kinds.most_common():
        print(f"{count:5} {kind:16} {samples[kind]}")


if __name__ == "__main__":
    main()
