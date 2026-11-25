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
for stride in (476, 478, 479, 480, 481, 482, 484):
    nrows = len(blocks) // stride
    if nrows < 200:
        continue
    show = min(480, stride)
    grid = blocks[:nrows * stride].reshape(nrows, stride, 8)[:, :show]
    # pad to 480 for the decoder
    if show < 480:
        pad = np.zeros((nrows, 480 - show, 8), dtype=np.uint8)
        grid = np.concatenate([grid, pad], axis=1)
    image, _ = decode_dxt1(grid.reshape(-1, 8)[:270 * 480], 1920, 1080)
    crop = image[200:700, 1880:1920]
    Image.fromarray(crop).resize((crop.shape[1] * 4, crop.shape[0] * 4), Image.NEAREST).save(
        os.path.join(OUT, f"stride_{stride}.png")
    )
    print("stride", stride, "rows", nrows)
