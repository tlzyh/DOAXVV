# -*- coding: utf-8 -*-
blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "rb").read()
for label, at in (("WGT_body", 0x230), ("VtxLay", 0x2ED0), ("IdxLay", 0x2F40), ("GeoDecl", 0x250)):
    print(f"\n== {label} {at:#x}")
    window = blob[at:at + 160]
    print(window.hex())
# bone-like strings anywhere
cur = bytearray()
start = 0
found = []
for i, value in enumerate(blob):
    if 32 <= value < 127:
        if not cur:
            start = i
        cur.append(value)
    else:
        if len(cur) >= 4:
            text = cur.decode("ascii")
            if text.startswith(("n_", "j_", "Bip", "sk_", "bn_", "WGT", "bone")) or "mis" in text.lower():
                found.append((start, text))
        cur.clear()
print("\nbones", found[:40], "count", len(found))
