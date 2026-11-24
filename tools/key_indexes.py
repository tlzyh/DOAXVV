# -*- coding: utf-8 -*-
"""Find the cipher index of each live key, then brute a likely model file."""
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"
KNOWN = ("0adb01", "0156553e", "092ff0", "076a612e", "d655", "02ae6d22", "01abfe", "8d452e")
MAGICS = (b"TMC\x00", b"TLSK", b"GT1G", b"_M1G", b"_N1G", b"_A2G", b"_A1G", b"_S2G", b"DDS ", b"tdpa")


def key_of(index):
    dword = ((index * 0x77) // 11) & 0xFFFFFFFF
    return bytes(b for b in dword.to_bytes(4, "big") if b)


def plain_byte(cipher, key, index):
    mixed = SEED[index % len(SEED)]
    if key:
        mixed ^= key[index % len(key)]
    if cipher == 0 or cipher == mixed:
        return cipher
    return cipher ^ mixed


def main():
    wanted = {bytes.fromhex(item): item for item in KNOWN}
    found = {}
    for index in range(1, 16_000_000):
        key = key_of(index)
        if key in wanted and key not in found:
            found[key] = index
            print("index", index, wanted[key])
            if len(found) == len(wanted):
                break
    print("found", len(found), "of", len(wanted))

    # A mid-size HIGH file that is not ASF and not a known cipher pair.
    known_pairs = set()
    skip = set()
    target = None
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        if not (80_000 <= size <= 4_000_000):
            continue
        head = open(full, "rb").read(16)
        if head.startswith(bytes.fromhex("3026b2758e66cf11")):
            continue
        target = (full, head, size)
        break
    print("target", os.path.basename(target[0])[:16], target[2], target[1][:8].hex())
    head = target[1]
    hits = []
    zlib_hits = []
    for index in range(1, 16_000_000):
        key = key_of(index)
        if not key:
            continue
        chars = bytes(plain_byte(head[i], key, i) for i in range(4))
        if chars in MAGICS:
            hits.append((index, key.hex(), chars))
            print("MAGIC", index, key.hex(), chars)
        elif len(zlib_hits) < 12 and plain_byte(head[4], key, 4) == 0x78 and plain_byte(head[5], key, 5) in (0x9C, 0xDA):
            zlib_hits.append((index, key.hex(), chars))
    print("magic hits", hits)
    print("zlib candidates", zlib_hits)
    hits.extend(zlib_hits)
    for index, key_hex, chars in hits:
        key = bytes.fromhex(key_hex)
        blob = open(target[0], "rb").read(65536)
        out = bytearray(blob)
        for i, value in enumerate(out):
            mixed = SEED[i % len(SEED)] ^ key[i % len(key)]
            if value != 0 and value != mixed:
                out[i] = value ^ mixed
        try:
            inflated = zlib.decompress(bytes(out[4:]))
            print("INFLATE", index, key_hex, inflated[:16])
        except zlib.error:
            print("noinflate", index, key_hex, bytes(out[:8]).hex())


if __name__ == "__main__":
    main()
