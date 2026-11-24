# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()
print("len", len(blob))
# print dwords of GeoDecl payload
base = 0x250
print("geodecl dwords")
for i in range(0, 0x180, 4):
    value = struct.unpack_from("<I", blob, base + i)[0]
    if i % 32 == 0:
        print(f"\n{base+i:04x}", end=" ")
    print(f"{value:08x}", end=" ")
print()
# find a stride where 3 consecutive floats look like a position
def looks(offset, stride, count=8):
    pts = []
    for n in range(count):
        x, y, z = struct.unpack_from("<fff", blob, offset + n * stride)
        if not all(-5 < v < 5 for v in (x, y, z)):
            return None
        pts.append((round(x, 3), round(y, 3), round(z, 3)))
    return pts

for offset in (0x4000, 0x4100, 0x5000, 0x8000, 0x98ac, 0x4000 + 16384):
    if offset + 64 >= len(blob):
        continue
    print("\nat", hex(offset), blob[offset:offset+16].hex())
    for stride in (12, 16, 20, 24, 28, 32, 36, 40, 48):
        pts = looks(offset, stride)
        if pts:
            print(" stride", stride, pts[:3])
