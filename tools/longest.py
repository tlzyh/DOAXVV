# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()


def runlen(offset, stride):
    n = 0
    ys = []
    while offset + (n + 1) * stride + 12 <= len(blob) and n < 8000:
        x, y, z = struct.unpack_from("<fff", blob, offset + n * stride)
        if x != x or abs(x) > 3 or abs(y) > 3 or abs(z) > 3:
            break
        ys.append(y)
        n += 1
    if n < 80:
        return None
    span = max(ys) - min(ys)
    # reject streams that are only -1/0/1
    varied = sum(1 for y in ys if abs(abs(y) - 1) > 0.05 and abs(y) > 0.05)
    if varied < n * 0.3 or span < 0.8:
        return None
    return n, span, min(ys), max(ys)


def main():
    best = []
    for stride in (32, 36, 40, 48, 64, 80):
        step = stride
        for base in range(0x4000, len(blob) - 1000, step):
            got = runlen(base, stride)
            if got:
                best.append((got[0], stride, base, got))
    best.sort(reverse=True)
    for row in best[:12]:
        n, stride, base, got = row
        print("count", n, "stride", stride, "base", hex(base), "spanY", round(got[1], 2), "y", round(got[2], 2), round(got[3], 2))


if __name__ == "__main__":
    main()
