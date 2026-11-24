# -*- coding: utf-8 -*-
"""Apply the live seed to COMMON and HIGH headers."""
import base64
import os
import struct

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
RAW = base64.b64decode(SEED)
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
MAGICS = (b"GT1G", b"_N1G", b"_M1G", b"_A2G", b"_A1G", b"OC1G", b"DDS ", b"RIFF")


def mix_at(seed, index, key):
    value = seed[index % len(seed)]
    if key:
        value ^= key[index % len(key)]
    return value


def head(blob, size, seed, key, origin):
    out = bytearray(blob)
    for pos, val in enumerate(blob):
        index = origin + pos
        mixed = mix_at(seed, index, key)
        if val and val != mixed:
            out[pos] = val ^ mixed
    return bytes(out)


def file_key(index):
    dword = (index * 0x77) // 11
    return bytes(b for b in dword.to_bytes(4, "big") if b)


def main():
    keys = [b""] + [file_key(i) for i in range(1, 64)]
    seeds = (("ascii", SEED), ("raw", RAW))
    hits = 0
    checked = 0
    for folder in ("COMMON", "HIGH"):
        path = os.path.join(ROOT, folder)
        for name in os.listdir(path):
            full = os.path.join(path, name)
            size = os.path.getsize(full)
            if size < 16 or size > 8_000_000:
                continue
            with open(full, "rb") as handle:
                blob = handle.read(32)
            if blob[:4] in (b"_L1G", b"NmGr") or blob[:4] == b"\x00\x00\x00\x00":
                continue
            checked += 1
            for label, seed in seeds:
                for key in keys:
                    for origin in (size, 0):
                        out = head(blob, size, seed, key, origin)
                        if out[:4] in MAGICS or out[4:8] in MAGICS or out[:2] in (b"\x78\x9c", b"\x78\xda"):
                            print("HIT", folder, name[:16], label, key.hex(), origin, out[:16])
                            hits += 1
                            if hits > 20:
                                return
    print("checked", checked, "hits", hits)


if __name__ == "__main__":
    main()
