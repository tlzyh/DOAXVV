# -*- coding: utf-8 -*-
"""Brute cipher indexes against one large file and confirm with inflate."""
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
LIMIT = 2_000_000


def key_of(index):
    dword = ((index * 0x77) // 11) & 0xFFFFFFFF
    raw = dword.to_bytes(4, "big")
    return bytes(b for b in raw if b)


def main():
    folder = os.path.join(ROOT, "COMMON")
    target = None
    for name in os.listdir(folder):
        full = os.path.join(folder, name)
        if os.path.getsize(full) > 5_000_000:
            target = full
            break
    head = open(target, "rb").read(8192)
    print("file", os.path.basename(target)[:16], "read", len(head))
    c4, c5 = head[4], head[5]
    s4, s5 = SEED[4], SEED[5]
    hits = []
    for index in range(1, LIMIT):
        key = key_of(index)
        length = len(key)
        if not length:
            continue
        mixed4 = s4 ^ key[4 % length]
        plain4 = c4 if c4 == 0 or c4 == mixed4 else c4 ^ mixed4
        if plain4 != 0x78:
            continue
        mixed5 = s5 ^ key[5 % length]
        plain5 = c5 if c5 == 0 or c5 == mixed5 else c5 ^ mixed5
        if plain5 not in (0x9C, 0xDA):
            continue
        # verify
        out = bytearray(head)
        nseed = len(SEED)
        for i, value in enumerate(out):
            mixed = SEED[i % nseed] ^ key[i % length]
            if value != 0 and value != mixed:
                out[i] = value ^ mixed
        try:
            inflated = zlib.decompress(bytes(out[4:]))
        except zlib.error:
            continue
        hits.append((index, key.hex(), len(inflated), inflated[:12]))
        print("HIT", hits[-1])
        if len(hits) >= 3:
            break
    print("done", len(hits))


if __name__ == "__main__":
    main()
