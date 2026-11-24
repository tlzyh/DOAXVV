# -*- coding: utf-8 -*-
blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()
for at in range(0x2C0, 0x2ED0, 16):
    print(f"{at:04x} {blob[at:at+16].hex()}")
