# -*- coding: utf-8 -*-
"""Describe the structured prefix of every shared-pool size."""
import collections
import os
import struct

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"


def main():
    chosen = {}
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        if size in chosen or size < 16:
            continue
        head = open(full, "rb").read(64)
        if head[4:6] == bytes((0x4A, 0x7B)) and head[2:4] == b"\x00\x00":
            chosen[size] = head
    print("sizes", len(chosen))
    stable = []
    for index in range(64):
        values = {head[index] for head in chosen.values()}
        if len(values) == 1:
            stable.append((index, next(iter(values))))
    print("stable", stable)
    rows = []
    for size, head in chosen.items():
        count = struct.unpack_from("<I", head, 0)[0]
        rows.append((count, size, size / count if count else 0))
    rows.sort()
    print("count size ratio")
    for count, size, ratio in rows[:8]:
        print(f"  {count:6} {size:8} {ratio:.3f}")
    print("  ...")
    for count, size, ratio in rows[-4:]:
        print(f"  {count:6} {size:8} {ratio:.3f}")
    # Does count * 16 divide the payload after a fixed header?
    for header in (8, 16, 32, 64, 256, 1472):
        good = 0
        for count, size, _ratio in rows:
            payload = size - header
            if count and payload > 0 and payload % count == 0:
                good += 1
        print("header", header, "divisible", good)


if __name__ == "__main__":
    main()
