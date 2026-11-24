# -*- coding: utf-8 -*-
import os

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"
PAIR = bytes.fromhex("4a7b")


def main():
    rows = []
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        head = open(full, "rb").read(32)
        if head[4:6] != PAIR:
            continue
        rows.append((size, name[:16], head))
        if len(rows) >= 6:
            break
    for size, name, head in rows:
        print(size, name, head.hex())
    # how far the first two agree
    a = rows[0][2]
    b = rows[1][2]
    n = 0
    while n < len(a) and a[n] == b[n]:
        n += 1
    print("shared", n)


if __name__ == "__main__":
    main()
