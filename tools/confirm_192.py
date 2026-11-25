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
jump = np.abs(image[:, 1:].astype(int) - image[:, :-1].astype(int)).mean(axis=(0, 2))
x = int(np.argmax(jump)) + 1
print("no align seam", x, round(float(jump[x - 1]), 1))

rolled = np.roll(image, 192, axis=1)
jump2 = np.abs(rolled[:, 1:].astype(int) - rolled[:, :-1].astype(int)).mean(axis=(0, 2))
print("after +192 top seams", [(int(i + 1), round(float(jump2[i]), 1)) for i in np.argsort(jump2)[::-1][:4]])
Image.fromarray(rolled).resize((960, 540), Image.BILINEAR).save(r"D:\Projects\YangHui\DOAXVV\export\_roll\raw192.jpg", quality=80)

# Same-row block roll of 48, which is the raw decode rolled by 192.
rows = len(blocks) // 480
grid = blocks[:rows * 480].reshape(rows, 480, 8)
moved = np.roll(grid, 48, axis=1)
image2, _ = decode_dxt1(moved.reshape(-1, 8), 1920, 1080)
print("block roll matches pixel roll", np.array_equal(image2, rolled[: image2.shape[0]]))
