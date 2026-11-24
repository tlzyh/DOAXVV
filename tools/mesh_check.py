# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()
BASE = 0x14A40
STRIDE = 32
COUNT = 1315


def main():
    xs, ys, zs = [], [], []
    for n in range(COUNT):
        x, y, z = struct.unpack_from("<fff", blob, BASE + n * STRIDE)
        xs.append(x)
        ys.append(y)
        zs.append(z)
    print("bbox", round(min(xs), 3), round(max(xs), 3), round(min(ys), 3), round(max(ys), 3), round(min(zs), 3), round(max(zs), 3))
    for n in (0, 1, 2, 100, 500, 1000):
        print(n, struct.unpack_from("<8f", blob, BASE + n * STRIDE))
    end = BASE + COUNT * STRIDE
    print("end", hex(end))
    # longest u16 run whose values are < COUNT
    best = (0, 0)
    n = 0
    start = 0
    for i in range(0, len(blob) - 1, 2):
        value = struct.unpack_from("<H", blob, i)[0]
        if value < COUNT:
            if n == 0:
                start = i
            n += 1
        else:
            if n > best[0]:
                best = (n, start)
            n = 0
    if n > best[0]:
        best = (n, start)
    print("best u16 run", best, "tris", best[0] // 3)


if __name__ == "__main__":
    main()
