# -*- coding: utf-8 -*-
"""Retry archive keys on files whose first zlib chunk did not fit in 8KB."""
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"


def apply(data, key):
    out = bytearray(len(data))
    for i, value in enumerate(data):
        mixed = SEED[i % len(SEED)] ^ key[i % len(key)]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def strings(blob):
    found = []
    cur = bytearray()
    for value in blob[:8000]:
        if 32 <= value < 127:
            cur.append(value)
        else:
            if len(cur) >= 5 and any(chr(b).isalpha() for b in cur):
                found.append(cur.decode("ascii"))
            cur.clear()
            if len(found) >= 6:
                break
    return found


def try_key(folder, pair, key, limit=8):
    print("\n==", folder, pair.hex(), key.hex())
    shown = 0
    ok = 0
    bad = 0
    for name in os.listdir(os.path.join(ROOT, folder)):
        full = os.path.join(ROOT, folder, name)
        size = os.path.getsize(full)
        if size < 32:
            continue
        head = open(full, "rb").read(6)
        if head[4:6] != pair:
            continue
        data = open(full, "rb").read(min(size, 262144))
        plain = apply(data, key)
        try:
            inflated = zlib.decompress(plain[4:])
        except zlib.error:
            bad += 1
            continue
        ok += 1
        if shown < limit:
            print(name[:16], size, len(inflated), inflated[:8], strings(inflated))
            shown += 1
    print("ok", ok, "bad", bad)


def main():
    try_key("HIGH", bytes.fromhex("0d81"), bytes.fromhex("8d452e"))
    try_key("HIGH", bytes.fromhex("0dc7"), bytes.fromhex("8d452e"))
    try_key("COMMON", bytes.fromhex("49f9"), bytes.fromhex("0156553e"), limit=4)


if __name__ == "__main__":
    main()
