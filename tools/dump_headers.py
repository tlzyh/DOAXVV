# -*- coding: utf-8 -*-
import csv
import os
import struct

from export_bromides import LIST, ROOT, decrypt_np
from decrypt import iter_pages

names = (
    "BROMIDE_4th_anniversary",
    "BROMIDE_EVENT_NNM_2024_zy_65_b",
    "BROMIDE_OWN_ZA_91_A_LUN",
    "BROMIDE_AYA_DF_00_A",
)
rows = {item["name"]: item for item in csv.DictReader(open(LIST, encoding="utf-8"))}
for name in names:
    row = rows[name]
    pages = [page for _pos, page in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
    page = pages[0]
    end = page.find(b"\x00", 0x8C)
    print("\n", name, "null", hex(end))
    pos = end + 1
    for i in range(16):
        value = struct.unpack_from("<I", page, pos + i * 4)[0]
        print(f"  +{i*4:02x} {value:10d}  {value:#010x}")
