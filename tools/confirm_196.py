# -*- coding: utf-8 -*-
import csv
import os

import numpy as np
from PIL import Image

from export_bromides import LIST, ROOT, decrypt_np, dxt_blocks, decode_dxt1
from decrypt import iter_pages

name = "BROMIDE_4th_anniversary"
row = next(item for item in csv.DictReader(open(LIST, encoding="utf-8")) if item["name"] == name)
pages = [page for _pos, page in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
blocks = dxt_blocks(b"".join(pages[1:]))
image, _ = decode_dxt1(blocks, 1920, 1080)
for shift in (192, 196, 188, 200):
    rolled = np.roll(image, shift, axis=1)
    jump = np.abs(rolled[:, 1:].astype(int) - rolled[:, :-1].astype(int)).mean(axis=(0, 2))
    # ignore the outer edge by looking at max in 8..1912
    inner = jump[8:1912]
    x = int(np.argmax(inner)) + 8
    print("shift", shift, "inner max", round(float(inner.max()), 1), "at", x + 1)
Image.fromarray(np.roll(image, 196, axis=1)).resize((960, 540), Image.BILINEAR).save(
    r"D:\Projects\YangHui\DOAXVV\export\_roll\raw196.jpg", quality=85
)
