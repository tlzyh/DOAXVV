# -*- coding: utf-8 -*-
"""Single pass over DOAX_VV.exe for path-like format strings."""
EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
OUT = r"D:\Projects\YangHui\DOAXVV\tools\_formats.txt"

data = open(EXE, "rb").read()
hits = []
i = 0
n = len(data)
while i < n:
    if 32 <= data[i] < 127:
        j = i
        while j < n and 32 <= data[j] < 127:
            j += 1
        if 2 <= j - i <= 96 and data[i:j].find(b"%") >= 0:
            text = data[i:j].decode("ascii")
            low = text.lower()
            if any(token in low for token in ("%s", "%x", "%02", "%08", "%16", "hash", ".bin", "dx11", "common")):
                hits.append(text)
        i = j
    else:
        i += 1

unique = []
seen = set()
for item in hits:
    if item not in seen:
        seen.add(item)
        unique.append(item)
open(OUT, "w", encoding="utf-8").write("\n".join(unique))
print("count", len(unique))
