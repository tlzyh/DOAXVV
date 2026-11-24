# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()


def score(offset, stride, count):
    xs, ys, zs = [], [], []
    for n in range(count):
        at = offset + n * stride
        if at + 12 > len(blob):
            return None
        x, y, z = struct.unpack_from("<fff", blob, at)
        if x != x or abs(x) > 8 or abs(y) > 8 or abs(z) > 8:
            return None
        xs.append(x)
        ys.append(y)
        zs.append(z)
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def main():
    hits = []
    for stride in (28, 32, 36, 40, 44, 48, 56, 64, 72, 80):
        for base in range(0x4000, 0x18000, 4):
            box = score(base, stride, 1500)
            if not box:
                continue
            span_y = box[3] - box[2]
            span_x = box[1] - box[0]
            if span_y > 1.2 and span_x > 0.2:
                hits.append((span_y, base, stride, box))
    hits.sort(key=lambda item: (item[2], item[1]))
    # keep the earliest base per stride
    seen = set()
    for span, base, stride, box in hits:
        if stride in seen:
            continue
        seen.add(stride)
        print("stride", stride, "base", hex(base), "spanY", round(span, 2), tuple(round(v, 3) for v in box))
    print("total", len(hits))


if __name__ == "__main__":
    main()
