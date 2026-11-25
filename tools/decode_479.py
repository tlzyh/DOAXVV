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
stride = 479
nrows = len(blocks) // stride
grid = blocks[:nrows * stride].reshape(nrows, stride, 8)
width = stride * 4
height = nrows * 4
image, _ = decode_dxt1(grid.reshape(-1, 8), width, height)
print("image", image.shape)
Image.fromarray(image).resize((width // 2, height // 2), Image.BILINEAR).save(os.path.join(OUT, "aya479.jpg"), quality=85)
crop = image[200:700, -40:]
Image.fromarray(crop).resize((crop.shape[1] * 4, crop.shape[0] * 4), Image.NEAREST).save(os.path.join(OUT, "aya479_R.png"))
crop = image[200:700, :40]
Image.fromarray(crop).resize((crop.shape[1] * 4, crop.shape[0] * 4), Image.NEAREST).save(os.path.join(OUT, "aya479_L.png"))
