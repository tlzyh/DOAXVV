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

def emit(label, grid):
    image, _ = decode_dxt1(grid.reshape(-1, 8), 1920, 1080)
    Image.fromarray(image).resize((960, 540), Image.BILINEAR).save(os.path.join(OUT, label + ".jpg"), quality=80)
    crop = image[200:700, 1888:1920]
    Image.fromarray(crop).resize((crop.shape[1] * 4, crop.shape[0] * 4), Image.NEAREST).save(os.path.join(OUT, label + "_R.png"))
    crop = image[200:700, :32]
    Image.fromarray(crop).resize((crop.shape[1] * 4, crop.shape[0] * 4), Image.NEAREST).save(os.path.join(OUT, label + "_L.png"))

# Right block of the previous row becomes the left block of this row.
moved = np.zeros_like(grid)
moved[0, 1:] = grid[0, :-1]
moved[1:, 0] = grid[:-1, -1]
moved[1:, 1:] = grid[1:, :-1]
emit("cross", moved)

# Opposite: left block of the next row becomes the right block of this row.
back = np.zeros_like(grid)
back[:-1, :-1] = grid[:-1, 1:]
back[:-1, -1] = grid[1:, 0]
back[-1, :-1] = grid[-1, 1:]
emit("crossback", back)
print("done")
