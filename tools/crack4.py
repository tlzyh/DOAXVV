# -*- coding: utf-8 -*-
"""Brute the free half of a 4-byte key for one locked file."""
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(__file__))
from decrypt import SEED, decrypt, magic_of

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"


def find(folder, prefix):
    path = os.path.join(ROOT, folder)
    for name in os.listdir(path):
        if name.startswith(prefix):
            return os.path.join(path, name)
    raise SystemExit(prefix)


def promising(blob):
    try:
        zlib.decompress(blob)
        return True
    except zlib.error as exc:
        text = str(exc)
        return "incomplete" in text or "truncated" in text


def main():
    folder, prefix, k0, k1 = sys.argv[1:5]
    k0, k1 = int(k0, 16), int(k1, 16)
    path = find(folder, prefix)
    data = open(path, "rb").read(min(os.path.getsize(path), 24000))
    print("file", os.path.basename(path)[:16], "size", os.path.getsize(path))
    tested = 0
    for b2 in range(256):
        for b3 in range(256):
            key = bytes((k0, k1, b2, b3))
            short = decrypt(data[:48], key)
            if short[4] != 0x78 or short[5] not in (0x9C, 0xDA):
                continue
            if not promising(short[4:]):
                continue
            tested += 1
            plain = decrypt(data, key)
            try:
                inflated = zlib.decompress(plain[4:])
            except zlib.error:
                continue
            print("HIT", key.hex(), len(inflated), magic_of(inflated), inflated[:12])
            return
    print("no hit, promising", tested)


if __name__ == "__main__":
    main()
