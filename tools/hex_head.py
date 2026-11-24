# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()
for at in range(0x40, 0x1A0, 16):
    floats = struct.unpack_from("<4f", blob, at)
    print(f"{at:04x} {blob[at:at+16].hex()}  {tuple(round(v, 4) for v in floats)}")
