# -*- coding: utf-8 -*-
"""Find the archive index that turns a COMMON header into a resource magic."""
import base64
import os

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
RAW = base64.b64decode(SEED)
COMMON = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
MAGICS = (b"GT1G", b"_N1G", b"_A2G", b"_A1G", b"OC1G", b"DDS ")


def key_of(index):
    dword = (index * 0x77) // 11
    return bytes(b for b in dword.to_bytes(4, "big") if b)


def plain_at(cipher, seed, key, origin):
    out = bytearray(len(cipher))
    for pos, value in enumerate(cipher):
        mixed = seed[(origin + pos) % len(seed)]
        if key:
            mixed ^= key[(origin + pos) % len(key)]
        if value and value != mixed:
            value ^= mixed
        out[pos] = value
    return bytes(out)


def main():
    name = next(entry for entry in os.listdir(COMMON) if entry.startswith("0030753cd83f82d7"))
    path = os.path.join(COMMON, name)
    cipher = open(path, "rb").read(24)
    seeds = (("ascii", SEED), ("raw", RAW))
    for index in list(range(1, 200000)) + [0x14100, 0xF538, 0x13070, 0x34968, 0xD9E0, 0x12C10]:
        key = key_of(index)
        if not key:
            continue
        for label, seed in seeds:
            for start in (0, 4, 5, 8, 12, 16):
                window = cipher[start:start + 8]
                for origin in (0, start):
                    out = plain_at(window, seed, key, origin)
                    if out[:4] in MAGICS or out[:2] == b"\x78\x9c":
                        # reject the two-zero zlib false pattern
                        if out[:2] == b"\x78\x9c" and out[2:4] == b"\x00\x00":
                            continue
                        print("HIT", index, label, key.hex(), start, origin, out)
                        return
    print("no hit")


if __name__ == "__main__":
    main()
