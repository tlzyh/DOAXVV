# -*- coding: utf-8 -*-
"""Treat the plaintext-looking header count as a cipher index."""
import os
import struct
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"


def key_of(index):
    dword = ((index * 0x77) // 11) & 0xFFFFFFFF
    return bytes(b for b in dword.to_bytes(4, "big") if b)


def decrypt(data, key, origin=0):
    out = bytearray(len(data))
    for i, value in enumerate(data):
        mixed = SEED[(origin + i) % len(SEED)]
        if key:
            mixed ^= key[(origin + i) % len(key)]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def main():
    path = None
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        if os.path.getsize(full) == 2460000:
            path = full
            break
    data = open(path, "rb").read(65536)
    count = struct.unpack_from("<I", data, 0)[0]
    print("count", count, "key", key_of(count).hex())
    for origin in (0, 4, 8, 16):
        plain = decrypt(data, key_of(count), origin)
        print("origin", origin, plain[:16].hex())
        for start in (0, 4, 8, 16):
            if plain[start:start + 2] not in (b"\x78\x9c", b"\x78\xda"):
                continue
            try:
                out = zlib.decompress(plain[start:])
                print(" inflate", origin, start, len(out), out[:8])
            except zlib.error as exc:
                print(" zlib", origin, start, exc)


if __name__ == "__main__":
    main()
