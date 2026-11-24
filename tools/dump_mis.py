# -*- coding: utf-8 -*-
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
KEY = bytes.fromhex("0adb01")
PREFIXES = ("0712669473d7b6ec", "0a95b250eada1ebb", "8506c9df5c4116f1", "a2c751fd2e5de0c5")


def apply(data):
    out = bytearray(len(data))
    for i, value in enumerate(data):
        mixed = SEED[i % len(SEED)] ^ KEY[i % len(KEY)]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def strings(blob):
    found = []
    cur = bytearray()
    start = 0
    for i, value in enumerate(blob):
        if 32 <= value < 127:
            if not cur:
                start = i
            cur.append(value)
        else:
            if len(cur) >= 4:
                found.append(f"{start:#x} {cur.decode('ascii')}")
            cur.clear()
    return found


def main():
    for prefix in PREFIXES:
        for name in os.listdir(ROOT):
            if name.startswith(prefix):
                data = open(os.path.join(ROOT, name), "rb").read()
                inflated = zlib.decompress(apply(data)[4:])
                print("\n==", name[:16], "file", len(data), "out", len(inflated))
                print("\n".join(strings(inflated)[:40]))
                break


if __name__ == "__main__":
    main()
