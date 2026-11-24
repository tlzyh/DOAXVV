# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_mis_za.bin", "rb").read()
at = blob.find(b"WGT_body\x00")
print("wgt", hex(at))
window = blob[at:at + 0x120]
# find GeoDecl inside this window
rel = window.find(b"GeoDecl")
print("geodecl", hex(at + rel))
base = at + rel
print(blob[base:base + 0x160].hex())
# element-like increasing u16 offsets
raw = blob[base:base + 0x180]
for i in range(len(raw) - 8):
    off = struct.unpack_from("<H", raw, i)[0]
    nxt = struct.unpack_from("<H", raw, i + 8)[0] if i + 10 < len(raw) else 0
    if off == 0 and nxt == 0x14:
        print("table", hex(base + i), raw[i:i + 80].hex())
        break
