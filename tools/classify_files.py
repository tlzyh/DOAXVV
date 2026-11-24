# -*- coding: utf-8 -*-
"""Group hash files by header and by which live key opens a TLSK zlib."""
import collections
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
KEYS = [
    bytes.fromhex(item)
    for item in (
        "0adb01",
        "092ff0",
        "076a612e",
        "d655",
        "02ae6d22",
        "01abfe",
        "0156553e",
        "8d452e",
    )
]
ASF = bytes.fromhex("3026b2758e66cf11a6d900aa0062ce6c")
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"


def plain_at(cipher, key, index):
    mixed = SEED[index % len(SEED)]
    if key:
        mixed ^= key[index % len(key)]
    if cipher == 0 or cipher == mixed:
        return cipher
    return cipher ^ mixed


def opens(head, key):
    return plain_at(head[4], key, 4) == 0x78 and plain_at(head[5], key, 5) in (0x9C, 0xDA, 0x01)


def main():
    by_head = collections.Counter()
    by_key = collections.Counter()
    examples = {key.hex(): [] for key in KEYS}
    other = []
    sizes = collections.Counter()
    for rel in ("COMMON", "HIGH", os.path.join("DL", "COMMON"), os.path.join("DL", "HIGH")):
        folder = os.path.join(ROOT, rel)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            size = os.path.getsize(full)
            sizes[rel] += 1
            with open(full, "rb") as handle:
                head = handle.read(16)
            if head.startswith(ASF):
                by_head[(rel, "asf")] += 1
                continue
            if size == 80:
                by_head[(rel, "rec80")] += 1
                continue
            if size <= 64:
                by_head[(rel, "tiny")] += 1
                continue
            opened = None
            for key in KEYS:
                if len(head) >= 6 and opens(head, key):
                    opened = key.hex()
                    break
            if opened:
                by_key[(rel, opened)] += 1
                if len(examples[opened]) < 3:
                    examples[opened].append((rel, name[:16], size))
            else:
                by_head[(rel, "other")] += 1
                if len(other) < 12:
                    other.append((rel, name[:16], size, head.hex()))
    print("counts", dict(sizes))
    print("--- keys ---")
    for key, count in sorted(by_key.items(), key=lambda item: -item[1]):
        print(count, key, examples[key[1]])
    print("--- heads ---")
    for key, count in sorted(by_head.items(), key=lambda item: -item[1]):
        print(count, key)
    print("--- other ---")
    for row in other:
        print(row)


if __name__ == "__main__":
    main()
