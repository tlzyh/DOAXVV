# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()


def box_f32(offset, stride, count):
    xs, ys, zs = [], [], []
    for n in range(count):
        at = offset + n * stride
        if at + 12 > len(blob):
            return None
        x, y, z = struct.unpack_from("<fff", blob, at)
        if x != x or abs(x) > 5 or abs(y) > 5 or abs(z) > 5:
            return None
        xs.append(x)
        ys.append(y)
        zs.append(z)
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def main():
    found = 0
    for stride in (80, 64, 48, 44, 40, 36, 32):
        for base in range(0x4000, min(len(blob) - stride * 400, 0x28000), 4):
            box = box_f32(base, stride, 400)
            if not box:
                continue
            span_y = box[3] - box[2]
            span_x = box[1] - box[0]
            if span_y > 1.0 and span_x > 0.15:
                print("f32", hex(base), stride, tuple(round(v, 2) for v in box))
                found += 1
                if found >= 12:
                    return
    print("none", found)


if __name__ == "__main__":
    main()
