# -*- coding: utf-8 -*-
import collections
import math
import os

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"
NEEDLES = (
    b"OggS", b"RIFF", b"fLaC", b"CRID", b"USM@", b"@UTF", b"KTSS", b"HCA\x00",
    b"DDS ", b"GT1G", b"_M1G", b"TLSK", b"TMC\x00", b"CONTE", b"clip", b"\x78\x9c",
    b"ftyp", b"moov", b"WAVEfmt",
)


def entropy(blob):
    counts = collections.Counter(blob)
    total = len(blob)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def main():
    path = None
    for name in os.listdir(ROOT):
        if name.startswith("00222073b44a4f02"):
            path = os.path.join(ROOT, name)
            break
    data = open(path, "rb").read()
    print("size", len(data), "entropy", round(entropy(data), 3), "head_entropy", round(entropy(data[:4096]), 3))
    print("zeros", data.count(b"\x00") )
    for needle in NEEDLES:
        print(needle, data.find(needle))
    print("u32 head")
    for i in range(0, 64, 4):
        print(i, int.from_bytes(data[i:i + 4], "little"), data[i:i + 4].hex())


if __name__ == "__main__":
    main()
