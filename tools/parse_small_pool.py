# -*- coding: utf-8 -*-
import os
import struct

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"


def main():
    path = next(
        os.path.join(ROOT, name)
        for name in os.listdir(ROOT)
        if os.path.getsize(os.path.join(ROOT, name)) == 17312
    )
    data = open(path, "rb").read()
    print("u32 head")
    for i in range(0, 256, 4):
        value = struct.unpack_from("<I", data, i)[0]
        mark = " *" if value == 0 or value < 100000 else ""
        print(f"{i:04x} {value:10d}{mark}")
    # zero-run positions
    runs = []
    n = 0
    start = 0
    for i, value in enumerate(data):
        if value == 0:
            if n == 0:
                start = i
            n += 1
        else:
            if n >= 8:
                runs.append((start, n))
            n = 0
    print("zero runs", len(runs))
    print(runs[:12], "...", runs[-4:])


if __name__ == "__main__":
    main()
