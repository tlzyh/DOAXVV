# -*- coding: utf-8 -*-
"""Crack the big HIGH group, including 4-byte keys."""
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"
PAIR = bytes.fromhex("4a7b")


def mixed_for(cipher, plain):
    if cipher == 0:
        return None if plain else 0
    return 0 if plain == cipher else cipher ^ plain


def apply(data, key):
    out = bytearray(len(data))
    n = len(SEED)
    k = len(key)
    for i, value in enumerate(data):
        mixed = SEED[i % n] ^ key[i % k]
        if value != 0 and value != mixed:
            out[i] = value ^ mixed
    return bytes(out)


def promising(blob):
    try:
        zlib.decompress(blob)
        return True
    except zlib.error as exc:
        text = str(exc)
        return "incomplete" in text or "truncated" in text


def main():
    sample = None
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        if size < 4096:
            continue
        head = open(full, "rb").read(6)
        if head[4:6] == PAIR:
            sample = open(full, "rb").read(min(size, 65536))
            print("sample", name[:16], size)
            break
    for plain in (0x9C, 0xDA):
        m4 = mixed_for(PAIR[0], 0x78)
        m5 = mixed_for(PAIR[1], plain)
        k0 = SEED[4] ^ m4
        k1 = SEED[5] ^ m5
        print("plain", hex(plain), "fixed", bytes((k0, k1)).hex())
        # keylen 4: key[0] at pos 4, key[1] at pos 5
        tested = 0
        for b2 in range(256):
            for b3 in range(256):
                key = bytes((k0, k1, b2, b3))
                short = apply(sample[:48], key)
                if short[4] != 0x78 or short[5] != plain:
                    continue
                if not promising(short[4:]):
                    continue
                tested += 1
                full = apply(sample, key)
                try:
                    inflated = zlib.decompress(full[4:])
                except zlib.error:
                    continue
                print("HIT", key.hex(), len(inflated), inflated[:24])
                return
        print("no hit, promising", tested)


if __name__ == "__main__":
    main()
