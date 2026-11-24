# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()


def bbox(offset, stride, count):
    xs, ys, zs = [], [], []
    for n in range(count):
        at = offset + n * stride
        if at + 12 > len(blob):
            break
        x, y, z = struct.unpack_from("<fff", blob, at)
        if x != x or abs(x) > 50 or abs(y) > 50 or abs(z) > 50:
            return None
        xs.append(x)
        ys.append(y)
        zs.append(z)
    if len(xs) < count // 2:
        return None
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs), len(xs))


def main():
    # GeoDecl says 0x1e43 = 7747 and 4 streams. Try nearby bases.
    for base in range(0x4000, 0xA000, 0x40):
        for stride in (32, 36, 40, 48, 64, 80):
            box = bbox(base, stride, 200)
            if not box:
                continue
            span_x = box[1] - box[0]
            span_y = box[3] - box[2]
            span_z = box[5] - box[4]
            if span_y > 0.4 and span_x > 0.05 and max(span_x, span_y, span_z) < 5:
                print(hex(base), "stride", stride, "x", round(box[0], 2), round(box[1], 2), "y", round(box[2], 2), round(box[3], 2), "z", round(box[4], 2), round(box[5], 2))


if __name__ == "__main__":
    main()
