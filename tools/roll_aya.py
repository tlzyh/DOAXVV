# -*- coding: utf-8 -*-
import csv
import os

import numpy as np
from PIL import Image

from export_bromides import LIST, ROOT, decrypt_np, dxt_blocks, decode_dxt1
from decrypt import iter_pages

OUT = r"D:\Projects\YangHui\DOAXVV\export\_phase"
name = "BROMIDE_AYA_DF_00_A"
row = next(item for item in csv.DictReader(open(LIST, encoding="utf-8")) if item["name"] == name)
pages = [page for _pos, page in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
blocks = dxt_blocks(b"".join(pages[1:]))
rows = len(blocks) // 480
grid = blocks[:rows * 480].reshape(rows, 480, 8)
for delta, label in ((0, "aya0"), (1, "aya1"), (-1, "ayam1")):
    rolled = np.roll(grid, delta, axis=1).reshape(-1, 8)
    image, _ = decode_dxt1(rolled, 1920, 1080)
    for edge, box in (("R", (1888, 200, 1920, 700)), ("L", (0, 200, 32, 700))):
        crop = image[box[1]:box[3], box[0]:box[2]]
        Image.fromarray(crop).resize((crop.shape[1] * 6, crop.shape[0] * 6), Image.NEAREST).save(
            os.path.join(OUT, f"{label}_{edge}.png")
        )
print("rows", rows)
