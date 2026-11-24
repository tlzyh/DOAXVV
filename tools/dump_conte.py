# -*- coding: utf-8 -*-
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"


def apply(data, key):
    out = bytearray(len(data))
    for i, value in enumerate(data):
        mixed = SEED[i % len(SEED)] ^ key[i % len(key)]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def strings(blob, limit=12):
    found = []
    cur = bytearray()
    for value in blob:
        if 32 <= value < 127:
            cur.append(value)
        else:
            if len(cur) >= 4 and any(chr(b).isalpha() for b in cur):
                found.append(cur.decode("ascii"))
            cur.clear()
            if len(found) >= limit:
                break
    return found


def main():
    jobs = ((bytes.fromhex("deb5"), bytes.fromhex("961a"), "CONTE"), (bytes.fromhex("06c1"), bytes.fromhex("4e6e"), "clip"))
    for pair, key, title in jobs:
        print("\n==", title)
        shown = 0
        mis = []
        for name in os.listdir(ROOT):
            full = os.path.join(ROOT, name)
            size = os.path.getsize(full)
            if size < 64:
                continue
            head = open(full, "rb").read(6)
            if head[4:6] != pair:
                continue
            data = open(full, "rb").read(min(size, 200000))
            try:
                inflated = zlib.decompress(apply(data, key)[4:])
            except zlib.error:
                continue
            text = strings(inflated)
            low = " ".join(text).lower()
            if shown < 8:
                print(name[:16], size, len(inflated), text[:6])
                shown += 1
            if "mis" in low or "body" in low or "mdl" in low or "swim" in low:
                mis.append((name[:16], text[:6]))
        print("interesting", mis[:20], "count", len(mis))


if __name__ == "__main__":
    main()
