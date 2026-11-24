# -*- coding: utf-8 -*-
"""See if the shared HIGH blobs use the mode-7 u16 chunk chain."""
import os
import struct

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"


def chunk_size(word):
    return ((word & 0x7FFF) + 0x13) & ~0xF


def walk(data):
    pos = 0
    sizes = []
    flags = []
    while pos + 2 <= len(data):
        word = struct.unpack_from("<H", data, pos)[0]
        size = chunk_size(word)
        if size < 16 or pos + size > len(data):
            return False, len(sizes), pos, sizes[:6], flags[:6]
        sizes.append(size)
        flags.append(word >> 15)
        pos += size
        if len(sizes) > 100000:
            return False, len(sizes), pos, sizes[:6], flags[:6]
    return pos == len(data), len(sizes), pos, sizes[:8], flags[:8]


def main():
    wanted = {}
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        if size in wanted or size < 16:
            continue
        head = open(full, "rb").read(6)
        if head[4:6] != bytes((0x4A, 0x7B)):
            continue
        wanted[size] = full
        if len(wanted) >= 8:
            break
    for size, full in sorted(wanted.items()):
        data = open(full, "rb").read()
        ok, count, pos, sizes, flags = walk(data)
        print(size, "ok", ok, "chunks", count, "pos", pos, "sizes", sizes, "hi", flags)


if __name__ == "__main__":
    main()
