# -*- coding: utf-8 -*-
import collections
import math
import os
import struct

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"


def main():
    path = None
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        if os.path.getsize(full) == 2460000:
            path = full
            break
    data = open(path, "rb").read()
    print("file", os.path.basename(path)[:16], len(data))
    for i in range(0, 160, 4):
        value = struct.unpack_from("<I", data, i)[0]
        print(f"{i:4} {value:10d} {data[i:i+4].hex()}")
    sample = data[4096:4096 + 65536]
    counts = collections.Counter(sample)
    entropy = -sum((n / len(sample)) * math.log2(n / len(sample)) for n in counts.values())
    print("entropy", round(entropy, 3), "zeros", sample.count(0))
    # cluster the 4a7b files by size + md5 of 4KB
    groups = collections.Counter()
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        if size < 16:
            continue
        head = open(full, "rb").read(6)
        if head[4:6] != bytes((0x4A, 0x7B)):
            continue
        groups[size] += 1
    print("distinct sizes", len(groups))
    for size, count in groups.most_common(12):
        print(f"  {count:4} x {size}")


if __name__ == "__main__":
    main()
