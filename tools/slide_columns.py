# -*- coding: utf-8 -*-
"""Use the contiguous DXT phase, then slide whole block columns."""
import csv
import os

import numpy as np
from PIL import Image

from export_bromides import LIST, ROOT, decrypt_np, decode_dxt1, image_info
from decrypt import iter_pages

NAME = "BROMIDE_EVENT_NNM_2024_zy_65_b"
OUT = r"D:\Projects\YangHui\DOAXVV\export\_phase"
MARKER = np.array([255, 255, 0, 0], dtype=np.uint8)


def save(name, image, box, scale=3):
    y0, y1, x0, x1 = box
    crop = image[y0:y1, x0:x1]
    Image.fromarray(crop).resize((crop.shape[1] * scale, crop.shape[0] * scale), Image.NEAREST).save(os.path.join(OUT, name))


def blocks_at(raw, shift, at):
    span = raw[shift:]
    count = len(span) // 16
    view = span[:count * 16].reshape(count, 16)
    dxt_index = np.arange(at - 8, at) % 16
    return view[:, dxt_index]


def main():
    row = {item["name"]: item for item in csv.DictReader(open(LIST, encoding="utf-8"))}[NAME]
    pages = [page for _pos, page in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
    raw = np.frombuffer(b"".join(pages[1:]), dtype=np.uint8)
    blocks = blocks_at(raw, 7, 12)
    print("contiguous blocks", len(blocks))
    grid = np.zeros((270, 480, 8), dtype=np.uint8)
    use = min(len(blocks), 270 * 480)
    grid.reshape(-1, 8)[:use] = blocks[:use]
    for delta in (0, 1, -1, 2, -2):
        rolled = np.roll(grid, delta, axis=1).reshape(-1, 8)
        image, _ = decode_dxt1(rolled, 1920, 1080)
        # discontinuity at the join created on the left
        join = abs(delta) * 4
        if join:
            seam = np.abs(image[:, join].astype(int) - image[:, join - 1].astype(int)).mean()
        else:
            seam = np.abs(image[:, 0].astype(int) - image[:, -1].astype(int)).mean()
        print("delta", delta, "seam", round(float(seam), 3))
        save(f"sharp_d{delta}_right.png", image, (180, 620, 1872, 1920), 4)
        save(f"sharp_d{delta}_left.png", image, (180, 620, 0, 48), 4)
        if delta in (0, 1, -1):
            Image.fromarray(image).save(os.path.join(OUT, f"sharp_d{delta}.png"), compress_level=1)


if __name__ == "__main__":
    main()
