# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_mis_za.bin", "rb").read()


def window(at, stride):
    xs, ys, zs, mags = [], [], [], []
    for i in range(250):
        pos = at + i * stride
        if pos + 12 > len(blob):
            return None
        x, y, z = struct.unpack_from("<fff", blob, pos)
        if x != x or abs(x) > 3 or abs(y) > 3 or abs(z) > 3:
            return None
        xs.append(x)
        ys.append(y)
        zs.append(z)
        mags.append((x * x + y * y + z * z) ** 0.5)
    mags.sort()
    median = mags[len(mags) // 2]
    span_y = max(ys) - min(ys)
    span_x = max(xs) - min(xs)
    if span_y < 0.35 or span_x < 0.08 or 0.9 < median < 1.1:
        return None
    return span_y, span_x, median, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def main():
    shown = 0
    for stride in (12, 32, 80):
        at = 0x4000
        while at + stride * 250 < len(blob):
            got = window(at, stride)
            if got:
                print(hex(at), stride, tuple(round(v, 3) for v in got))
                shown += 1
                if shown >= 8:
                    return
                at += stride * 250
            else:
                at += stride
    print("shown", shown)


if __name__ == "__main__":
    main()
