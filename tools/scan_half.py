# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()


def run(fmt, size, stride, lo, hi):
    best = (0, 0)
    n = 0
    start = 0
    for align in range(0, stride, 2):
        at = 0x4000 + align
        n = 0
        while at + size <= len(blob):
            vals = struct.unpack_from(fmt, blob, at)
            if all(lo < v < hi and v == v for v in vals) and max(abs(v) for v in vals) > 0.02:
                if n == 0:
                    start = at
                n += 1
            else:
                if n > best[0]:
                    best = (n, start, stride)
                n = 0
            at += stride
        if n > best[0]:
            best = (n, start, stride)
    return best


def main():
    for stride in (12, 16, 24, 32, 40):
        count, start, _ = run("<eee", 6, stride, -4, 4)
        print("half", stride, count, hex(start))
        count, start, _ = run("<hhh", 6, stride, -32000, 32000)
        print("i16", stride, count, hex(start))


if __name__ == "__main__":
    main()
