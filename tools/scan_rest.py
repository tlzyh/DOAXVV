# -*- coding: utf-8 -*-
"""Phase-0 decrypt of files that the known cipher pairs did not open."""
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
KEYS = [bytes.fromhex(item) for item in ("0adb01", "0156553e", "092ff0", "076a612e", "d655", "02ae6d22", "01abfe", "8d452e")]
MAGICS = (b"TMC\x00", b"TLSK", b"GT1G", b"_M1G", b"_N1G", b"_A2G", b"_A1G", b"_S2G", b"DDS ", b"tdpa")
ASF = bytes.fromhex("3026b2758e66cf11")


def crypt(value, mixed):
    if value == 0 or value == mixed:
        return value
    return value ^ mixed


def cipher_pair(key, plain):
    out = bytearray()
    for i, value in enumerate(plain):
        index = 4 + i
        mixed = SEED[index % len(SEED)] ^ key[index % len(key)]
        out.append(crypt(value, mixed))
    return bytes(out)


def apply(data, key):
    out = bytearray(len(data))
    for i, value in enumerate(data):
        mixed = SEED[i % len(SEED)] ^ key[i % len(key)]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def main():
    skip = {cipher_pair(key, magic) for key in KEYS for magic in (b"\x78\x9c", b"\x78\xda")}
    hits = []
    checked = 0
    for rel in ("HIGH", "COMMON"):
        folder = os.path.join(ROOT, rel)
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            size = os.path.getsize(full)
            if size < 64:
                continue
            with open(full, "rb") as handle:
                head = handle.read(96)
            if head.startswith(ASF) or head[4:6] in skip:
                continue
            checked += 1
            for key in KEYS:
                plain = apply(head, key)
                found = None
                for magic in MAGICS:
                    at = plain.find(magic)
                    if 0 <= at <= 32:
                        found = (magic, at)
                        break
                zpos = plain.find(b"\x78\x9c")
                if zpos < 0:
                    zpos = plain.find(b"\x78\xda")
                if found is None and not (0 <= zpos <= 16):
                    continue
                blob = apply(open(full, "rb").read(min(size, 65536)), key)
                inflated = None
                if 0 <= zpos <= 16:
                    try:
                        inflated = zlib.decompress(blob[zpos:zpos + 65536])[:12]
                    except zlib.error:
                        inflated = None
                if found or inflated:
                    hits.append((rel, name[:16], size, key.hex(), found, zpos, inflated))
                    print("HIT", hits[-1])
                if len(hits) >= 15:
                    break
            if len(hits) >= 15:
                break
        if len(hits) >= 15:
            break
    print("checked", checked, "hits", len(hits))


if __name__ == "__main__":
    main()
