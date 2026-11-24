# -*- coding: utf-8 -*-
"""Separate real TLSK streams from two-byte header collisions."""
import collections
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
KEYS = {
    "0156553e": bytes.fromhex("0156553e"),
    "0adb01": bytes.fromhex("0adb01"),
    "aabbccdd": bytes.fromhex("aabbccdd"),
}


def plain_at(cipher, key, index):
    mixed = SEED[index % len(SEED)] ^ key[index % len(key)]
    if cipher == 0 or cipher == mixed:
        return cipher
    return cipher ^ mixed


def apply(data, key):
    out = bytearray(len(data))
    for i, value in enumerate(out if False else data):
        mixed = SEED[i % len(SEED)] ^ key[i % len(key)]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def main():
    folder = os.path.join(ROOT, "COMMON")
    stats = {name: collections.Counter() for name in KEYS}
    real = {name: 0 for name in KEYS}
    shown = {name: 0 for name in KEYS}
    for name in os.listdir(folder):
        full = os.path.join(folder, name)
        size = os.path.getsize(full)
        if size < 32:
            continue
        head = open(full, "rb").read(8)
        for key_name, key in KEYS.items():
            if plain_at(head[4], key, 4) == 0x78 and plain_at(head[5], key, 5) in (0x9C, 0xDA):
                stats[key_name][head[4:6].hex()] += 1
                if shown[key_name] < 3 or real[key_name] < 3:
                    blob = apply(open(full, "rb").read(min(size, 65536)), key)
                    try:
                        inflated = zlib.decompress(blob[4:])
                        ok = True
                    except zlib.error:
                        ok = False
                    if ok:
                        real[key_name] += 1
                        print("REAL", key_name, name[:16], size, inflated[:12])
                    shown[key_name] += 1
    for key_name, counter in stats.items():
        print(key_name, "pairs", sum(counter.values()), "unique_cipher", len(counter), "top", counter.most_common(3), "real_seen", real[key_name])


if __name__ == "__main__":
    main()
