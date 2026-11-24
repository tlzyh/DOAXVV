# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()


def window(at, stride, count):
    xs, ys, zs, mags = [], [], [], []
    for i in range(count):
        x, y, z = struct.unpack_from("<fff", blob, at + i * stride)
        if x != x or abs(x) > 5 or abs(y) > 5 or abs(z) > 5:
            return None
        xs.append(x)
        ys.append(y)
        zs.append(z)
        mags.append((x * x + y * y + z * z) ** 0.5)
    mags.sort()
    median = mags[len(mags) // 2]
    span_y = max(ys) - min(ys)
    span_x = max(xs) - min(xs)
    if span_y < 0.4 or span_x < 0.1:
        return None
    if 0.85 < median < 1.15:
        return None
    return span_y, span_x, median, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def main():
    hits = []
    for stride in (12, 16, 20, 24, 32, 40, 48, 80):
        limit = len(blob) - stride * 400
        for at in range(0, limit, stride):
            got = window(at, stride, 400)
            if got:
                hits.append((got[0], stride, at, got))
    hits.sort(reverse=True)
    seen = set()
    for span, stride, at, got in hits:
        key = (stride, at // 256)
        if key in seen:
            continue
        seen.add(key)
        print("stride", stride, "at", hex(at), "spanY", round(span, 2), "spanX", round(got[1], 2), "med", round(got[2], 2), "box", tuple(round(v, 2) for v in got[3:]))
        if len(seen) >= 10:
            break
    print("hits", len(hits))


if __name__ == "__main__":
    main()
