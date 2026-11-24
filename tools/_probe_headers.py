# -*- coding: utf-8 -*-
"""Read-only probe of DMM resource headers. Not part of the final tool."""
import collections
import os
import struct

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"


def main():
    hist = collections.Counter()
    by_key = collections.defaultdict(list)
    stringy = []
    n = 0
    for name in os.listdir(ROOT):
        path = os.path.join(ROOT, name)
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            head = handle.read(64)
        if len(head) < 4:
            continue
        key = struct.unpack_from("<I", head, 0)[0]
        n += 1
        hist[key] += 1
        if len(by_key[key]) < 3:
            by_key[key].append((size, name[:16], head[:32].hex()))
        # strings in the first 4 KB of a spread of files
        if n % 200 == 0 and size < 2_000_000:
            with open(path, "rb") as handle:
                blob = handle.read(min(size, 8192))
            text = []
            cur = bytearray()
            for byte in blob:
                if 32 <= byte < 127:
                    cur.append(byte)
                else:
                    if len(cur) >= 6:
                        text.append(cur.decode("ascii"))
                    cur = bytearray()
            if text:
                stringy.append((name[:16], size, text[:8]))
    print("files", n, "distinct first u32", len(hist))
    print("most common first u32:")
    for key, count in hist.most_common(20):
        print(f"  {count:5} 0x{key:08x}")
        for row in by_key[key]:
            print("   ", row)
    print("string samples", len(stringy))
    for row in stringy[:15]:
        print(row)


if __name__ == "__main__":
    main()
