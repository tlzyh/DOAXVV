# -*- coding: utf-8 -*-
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
    for value in blob[:20000]:
        if 32 <= value < 127:
            cur.append(value)
        else:
            if len(cur) >= 6 and sum(chr(b).isalnum() or chr(b) == "_" for b in cur) >= 6:
                found.append(cur.decode("ascii"))
            cur.clear()
            if len(found) >= 8:
                break
    return found


def main():
    jobs = (
        ("HIGH", bytes.fromhex("f03a"), bytes.fromhex("b895")),
        ("HIGH", bytes.fromhex("3c22"), bytes.fromhex("01748d")),
        ("HIGH", bytes.fromhex("452a"), bytes.fromhex("0d85")),
        ("HIGH", bytes.fromhex("4a7b"), b""),
    )
    for folder, pair, key in jobs:
        sizes = []
        shown = 0
        path = os.path.join(ROOT, folder)
        for name in os.listdir(path):
            full = os.path.join(path, name)
            size = os.path.getsize(full)
            head = open(full, "rb").read(6)
            if head[4:6] != pair:
                continue
            sizes.append(size)
            if key and shown < 3 and size > 32:
                try:
                    inflated = zlib.decompress(apply(open(full, "rb").read(min(size, 65536)), key)[4:])
                    print(folder, pair.hex(), name[:12], size, strings(inflated))
                except zlib.error as exc:
                    print(folder, pair.hex(), name[:12], size, "fail", exc)
                shown += 1
        sizes.sort()
        print(folder, pair.hex(), "count", len(sizes), "min", sizes[0] if sizes else None, "mid", sizes[len(sizes)//2] if sizes else None, "max", sizes[-1] if sizes else None)


if __name__ == "__main__":
    main()
