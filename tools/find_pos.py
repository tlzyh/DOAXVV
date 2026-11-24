# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()


def main():
    best = []
    for stride in (12, 16, 20, 24, 28, 32, 36, 40, 48, 64, 80):
        for align in range(0, stride, 4):
            n = 0
            start = 0
            at = align
            while at + 12 <= len(blob):
                x, y, z = struct.unpack_from("<fff", blob, at)
                mag2 = x * x + y * y + z * z
                ok = (
                    x == x and abs(x) < 4 and abs(y) < 4 and abs(z) < 4
                    and mag2 > 1e-4 and not (0.9 < mag2 < 1.1)
                )
                if ok:
                    if n == 0:
                        start = at
                    n += 1
                else:
                    if n >= 300:
                        best.append((n, stride, start))
                    n = 0
                at += stride
            if n >= 300:
                best.append((n, stride, start))
    best.sort(reverse=True)
    for count, stride, start in best[:12]:
        xs, ys, zs = [], [], []
        for i in range(min(count, 800)):
            x, y, z = struct.unpack_from("<fff", blob, start + i * stride)
            xs.append(x)
            ys.append(y)
            zs.append(z)
        print(
            "n", count, "stride", stride, "at", hex(start),
            "x", round(min(xs), 2), round(max(xs), 2),
            "y", round(min(ys), 2), round(max(ys), 2),
            "z", round(min(zs), 2), round(max(zs), 2),
        )


if __name__ == "__main__":
    main()
