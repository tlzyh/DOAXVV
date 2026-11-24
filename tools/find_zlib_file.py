# -*- coding: utf-8 -*-
"""See if any hash file becomes a zlib stream under the live keys."""
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
KEYS = [b""] + [
    bytes.fromhex(item)
    for item in ("092ff0", "076a612e", "d655", "02ae6d22", "01abfe", "0156553e", "8d452e", "0adb01")
]
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"


def stream(key):
    if not key:
        return SEED
    size = len(SEED) * len(key) // __import__("math").gcd(len(SEED), len(key))
    raw = bytearray(size)
    for i in range(size):
        raw[i] = SEED[i % len(SEED)] ^ key[i % len(key)]
    return bytes(raw)


def plain_byte(cipher, mixed):
    if cipher == 0 or cipher == mixed:
        return cipher
    return cipher ^ mixed


def main():
    prepared = [(key, stream(key)) for key in KEYS]
    hits = []
    checked = 0
    for folder in ("COMMON", "HIGH"):
        folder_path = os.path.join(ROOT, folder)
        for name in os.listdir(folder_path):
            full = os.path.join(folder_path, name)
            size = os.path.getsize(full)
            if size < 32 or size > 2_000_000:
                continue
            checked += 1
            with open(full, "rb") as handle:
                head = handle.read(64)
            for key, keystream in prepared:
                for start in (0, 4):
                    c0 = head[start]
                    if c0 == 0:
                        continue
                    # plain[0] must become 0x78
                    phases = []
                    for phase, mixed in enumerate(keystream):
                        if plain_byte(c0, mixed) == 0x78:
                            phases.append(phase)
                    for phase in phases:
                        c1 = head[start + 1]
                        mixed = keystream[(phase + 1) % len(keystream)]
                        if plain_byte(c1, mixed) not in (0x9C, 0xDA, 0x01):
                            continue
                        out = bytearray(head[start:])
                        for i, value in enumerate(out):
                            mixed = keystream[(phase + i) % len(keystream)]
                            out[i] = plain_byte(value, mixed)
                        if bytes(out[:2]) not in (b"\x78\x9c", b"\x78\xda", b"\x78\x01"):
                            continue
                        try:
                            inflated = zlib.decompress(bytes(out))
                        except zlib.error:
                            continue
                        hits.append((folder, name[:16], key.hex(), phase, start, len(inflated), inflated[:8]))
                        if len(hits) >= 8:
                            break
                    if len(hits) >= 8:
                        break
                if len(hits) >= 8:
                    break
            if len(hits) >= 8:
                break
        if len(hits) >= 8:
            break
    print("checked", checked, "hits", len(hits))
    for row in hits:
        print(row)


if __name__ == "__main__":
    main()
