# -*- coding: utf-8 -*-
import os

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
NEEDLES = (b"GT1G", b"_M1G", b"_N1G", b"_A2G", b"TLSK", b"DDS ", b"\x78\x9c")


def main():
    paths = []
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        if size > 5_000_000:
            paths.append((size, full))
        if len(paths) >= 2:
            break
    blobs = []
    for size, full in paths:
        data = open(full, "rb").read()
        blobs.append(data)
        print("\n", os.path.basename(full)[:16], size)
        print(" head", data[:32].hex())
        for needle in NEEDLES:
            at = data.find(needle)
            print(" ", needle, at)
    if len(blobs) == 2:
        n = min(len(blobs[0]), len(blobs[1]), 256)
        same = 0
        while same < n and blobs[0][same] == blobs[1][same]:
            same += 1
        print("shared prefix", same, blobs[0][:same].hex())


if __name__ == "__main__":
    main()
