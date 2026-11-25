# -*- coding: utf-8 -*-
import csv
import os

import numpy as np
from PIL import Image

from export_bromides import LIST, ROOT, decrypt_np, dxt_blocks, decode_dxt1
from decrypt import iter_pages

OUT = r"D:\Projects\YangHui\DOAXVV\export\_roll"
rows = {item["name"]: item for item in csv.DictReader(open(LIST, encoding="utf-8"))}
for name in ("BROMIDE_EVENT_NNM_2024_zy_65_b", "BROMIDE_AYA_DF_00_A", "BROMIDE_OWN_ZA_91_A_LUN"):
    row = rows[name]
    pages = [page for _pos, page in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
    blocks = dxt_blocks(b"".join(pages[1:]))
    image, _ = decode_dxt1(blocks, 1920, 1080)
    jump = np.abs(image[:, 1:].astype(int) - image[:, :-1].astype(int)).mean(axis=(0, 2))
    seam = int(np.argmax(jump)) + 1
    print(name, "seam", seam, round(float(jump[seam - 1]), 1))
    rolled = np.roll(image, 1920 - seam, axis=1)
    Image.fromarray(rolled).resize((960, 540), Image.BILINEAR).save(os.path.join(OUT, name[-16:] + ".jpg"), quality=80)
