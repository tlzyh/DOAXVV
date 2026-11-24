# -*- coding: utf-8 -*-
import os

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
PAIR = bytes.fromhex("f29c")


def main():
    shown = 0
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        head = open(full, "rb").read(24)
        if head[4:6] != PAIR:
            continue
        print(size, name[:12], head.hex())
        shown += 1
        if shown >= 6:
            break


if __name__ == "__main__":
    main()
