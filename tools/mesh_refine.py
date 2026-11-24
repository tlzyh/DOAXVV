# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()
STRIDE = 32


def is_pos(x, y, z):
    if x != x or y != y or z != z:
        return False
    if max(abs(x), abs(y), abs(z)) < 1e-3:
        return False
    if max(abs(x), abs(y), abs(z)) > 3:
        return False
    return True


def main():
    runs = []
    for align in range(0, STRIDE, 4):
        n = 0
        start = 0
        at = 0x4000 + align
        while at + 12 <= len(blob):
            x, y, z = struct.unpack_from("<fff", blob, at)
            if is_pos(x, y, z):
                if n == 0:
                    start = at
                n += 1
            else:
                if n >= 200:
                    runs.append((n, start))
                n = 0
            at += STRIDE
        if n >= 200:
            runs.append((n, start))
    runs.sort(reverse=True)
    for count, start in runs[:10]:
        xs, ys, zs = [], [], []
        for i in range(count):
            x, y, z = struct.unpack_from("<fff", blob, start + i * STRIDE)
            xs.append(x)
            ys.append(y)
            zs.append(z)
        print(
            "n", count, "at", hex(start),
            "x", round(min(xs), 2), round(max(xs), 2),
            "y", round(min(ys), 2), round(max(ys), 2),
            "z", round(min(zs), 2), round(max(zs), 2),
        )
        print("  v0", tuple(round(v, 3) for v in struct.unpack_from("<6f", blob, start)))


if __name__ == "__main__":
    main()
