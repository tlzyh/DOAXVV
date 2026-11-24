# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_mis_za.bin", "rb").read()


def report(label, at, stride, count=8):
    print("\n", label, hex(at), "stride", stride)
    xs, ys, zs = [], [], []
    ok = 0
    for i in range(min(count, 400)):
        if at + i * stride + 12 > len(blob):
            break
        x, y, z = struct.unpack_from("<fff", blob, at + i * stride)
        if i < 4:
            print(" ", i, tuple(round(v, 4) for v in (x, y, z)))
        if x == x and abs(x) < 5 and abs(y) < 5 and abs(z) < 5:
            xs.append(x)
            ys.append(y)
            zs.append(z)
            ok += 1
    if xs:
        print(" ok", ok, "x", round(min(xs), 3), round(max(xs), 3), "y", round(min(ys), 3), round(max(ys), 3), "z", round(min(zs), 3), round(max(zs), 3))


def main():
    for at in (0x6B28, 0x151D, 0x4000, 0x8403, 0x15B):
        if at < len(blob):
            report("f32", at, 12, 6)
            report("f32s80", at, 80, 4)
            report("f32s32", at, 32, 4)


if __name__ == "__main__":
    main()
