# -*- coding: utf-8 -*-
"""Measure per-type headers and try every zlib candidate in one file."""
import collections
import os
import struct
import zlib

COMMON = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"


def main():
    groups = collections.defaultdict(list)
    for name in os.listdir(COMMON):
        path = os.path.join(COMMON, name)
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            head = handle.read(48)
        if len(head) < 8:
            continue
        key = struct.unpack_from("<I", head, 0)[0]
        if key > 0xFFFF:
            continue
        groups[key].append((size, head))
    ranked = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    print("types", len(ranked))
    for key, rows in ranked[:12]:
        sizes = [row[0] for row in rows]
        prefix = rows[0][1]
        for _size, head in rows[1:]:
            n = min(len(prefix), len(head))
            cut = n
            for i in range(n):
                if prefix[i] != head[i]:
                    cut = i
                    break
            prefix = prefix[:cut]
        print(
            f"0x{key:04x} n={len(rows):4} size {min(sizes)}..{max(sizes)} "
            f"common {len(prefix)} {prefix[:16].hex()}"
        )

    # exhaustive zlib on one medium file that is not a fixed tiny record
    for name in os.listdir(COMMON):
        path = os.path.join(COMMON, name)
        size = os.path.getsize(path)
        if not (800_000 < size < 1_200_000):
            continue
        data = open(path, "rb").read()
        if data[:4] == b"_L1G" or data[:8] == bytes.fromhex("3026b2758e66cf11"):
            continue
        ok = 0
        for sig in (b"\x78\x9c", b"\x78\xda", b"\x78\x01"):
            start = 0
            while True:
                index = data.find(sig, start)
                if index < 0:
                    break
                start = index + 1
                try:
                    out = zlib.decompress(data[index:index + 200000])
                except zlib.error:
                    continue
                ok += 1
                print("zlib", name[:12], hex(index), len(out), out[:8])
                if ok >= 3:
                    return
        print("no zlib", name[:12], size)
        # look for an offset table in the first 256 bytes
        vals = struct.unpack_from("<64I", data, 0)
        inside = [v for v in vals if 16 < v < size]
        print(" u32s inside file", inside[:12])
        return


if __name__ == "__main__":
    main()
