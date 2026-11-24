# -*- coding: utf-8 -*-
import csv
import os
import struct
import zlib

import sys
sys.path.insert(0, os.path.dirname(__file__))
from decrypt import decrypt

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
rows = list(csv.DictReader(open(r"D:\Projects\YangHui\DOAXVV\tools\_bromide_list.csv", encoding="utf-8")))
want = {}
for row in rows:
    name = row["name"]
    if len(name) not in want and len(name) in (19, 22, 23, 26, 29, 33, 34):
        want[len(name)] = row
    if name.startswith("BROMIDE_SEAL") and "seal" not in want:
        want["seal"] = row

for key, row in want.items():
    path = os.path.join(ROOT, row["folder"], row["hash"])
    plain = decrypt(open(path, "rb").read(65536), bytes.fromhex(row["key"]))
    page = zlib.decompress(plain[4:])
    end = page.find(b"\x00", 0x8C)
    print("LEN", key, row["name"], "null", hex(end), "page", len(page))
    print(page[end:end + 48].hex())
    hits = []
    for i in range(0x80, min(len(page) - 2, 0x140), 2):
        value = struct.unpack_from("<H", page, i)[0]
        if value in (480, 640, 720, 768, 960, 1024, 1080, 1280, 1440, 1536, 1600, 1920, 2048):
            hits.append((hex(i), value))
    print("sizes", hits)
    print("u32", [(hex(end + 1 + i * 4), struct.unpack_from("<I", page, end + 1 + i * 4)[0]) for i in range(10)])
