# -*- coding: utf-8 -*-
blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()
for start, end in ((0x2E80, 0x3100), (0x230, 0x2B0)):
    print(f"\n{start:#x}")
    for at in range(start, end, 16):
        print(f"{at:04x} {blob[at:at+16].hex()}")
