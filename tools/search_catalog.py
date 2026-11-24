# -*- coding: utf-8 -*-
"""Look for a hash-to-key table inside files we can already decrypt."""
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
NEEDLE = bytes.fromhex("01bae222a50d5175")
INDEX = (65762).to_bytes(4, "little")


def apply(data, key):
    out = bytearray(len(data))
    for i, value in enumerate(data):
        mixed = SEED[i % len(SEED)] ^ key[i % len(key)]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def main():
    key = bytes.fromhex("0adb01")
    folder = os.path.join(ROOT, "COMMON")
    hits = 0
    scanned = 0
    for name in os.listdir(folder):
        if not name.startswith("01") and scanned > 0:
            pass
        full = os.path.join(folder, name)
        size = os.path.getsize(full)
        if size < 32 or size > 30000:
            continue
        head = open(full, "rb").read(6)
        if head[4:6] != bytes.fromhex("93ae"):
            continue
        data = open(full, "rb").read()
        try:
            inflated = zlib.decompress(apply(data, key)[4:])
        except zlib.error:
            continue
        scanned += 1
        at = inflated.find(NEEDLE)
        at2 = inflated.find(INDEX)
        if at >= 0 or (at2 >= 0 and inflated.count(INDEX) < 5):
            print("hit", name[:16], "hash", at, "index", at2)
            hits += 1
    print("scanned", scanned, "hits", hits)
    # plaintext records
    raw_hits = 0
    for name in os.listdir(folder):
        full = os.path.join(folder, name)
        if os.path.getsize(full) > 4096:
            continue
        blob = open(full, "rb").read()
        if NEEDLE in blob:
            print("raw", name[:16])
            raw_hits += 1
            if raw_hits >= 5:
                break
    print("raw hits", raw_hits)


if __name__ == "__main__":
    main()
