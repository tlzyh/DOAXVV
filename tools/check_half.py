# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()
start = 0x2DAEA
stride = 32
count = 200
xs, ys, zs = [], [], []
for i in range(count):
    x, y, z = struct.unpack_from("<eee", blob, start + i * stride)
    xs.append(x)
    ys.append(y)
    zs.append(z)
print("half bbox", min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
print("v0", struct.unpack_from("<8e", blob, start))
print("v1", struct.unpack_from("<8e", blob, start + stride))
print("v50", struct.unpack_from("<8e", blob, start + 50 * stride))
