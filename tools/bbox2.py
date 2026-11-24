# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()


def bbox(offset, stride, count):
    xs, ys, zs = [], [], []
    for n in range(count):
        at = offset + n * stride
        if at + 12 > len(blob):
            return None
        x, y, z = struct.unpack_from("<fff", blob, at)
        if x != x or abs(x) > 20 or abs(y) > 20 or abs(z) > 20:
            return None
        xs.append(x)
        ys.append(y)
        zs.append(z)
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def main():
    best = []
    for base in range(0x4000, 0x20000, 16):
        for stride in (32, 40, 48, 64, 80):
            box = bbox(base, stride, 300)
            if not box:
                continue
            span_x = box[1] - box[0]
            span_y = box[3] - box[2]
            span_z = box[5] - box[4]
            if span_y > 1.0 and 0.1 < span_x < span_y and span_z < span_y:
                best.append((span_y, base, stride, box))
    best.sort(reverse=True)
    for row in best[:15]:
        span, base, stride, box = row
        print(hex(base), "stride", stride, "spanY", round(span, 2), "box", tuple(round(v, 2) for v in box))


if __name__ == "__main__":
    main()
