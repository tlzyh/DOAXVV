# -*- coding: utf-8 -*-
"""Write two candidate fixes for the speckled Nyotengu bromide."""
import csv
import os

import numpy as np
from PIL import Image

from export_bromides import LIST, OUT_DIR, ROOT, decrypt_np, dxt_blocks, image_info, rgb565
from decrypt import iter_pages

NAME = "BROMIDE_EVENT_NYO_2025_zy_84_a"


def decode(blocks, mode):
    raw = blocks.astype(np.uint32)
    c0 = raw[:, 0] | (raw[:, 1] << 8)
    c1 = raw[:, 2] | (raw[:, 3] << 8)
    bits = raw[:, 4] | (raw[:, 5] << 8) | (raw[:, 6] << 16) | (raw[:, 7] << 24)
    col0 = rgb565(c0)
    col1 = rgb565(c1)
    if mode == "opaque":
        col2 = (2 * col0 + col1) // 3
        col3 = (col0 + 2 * col1) // 3
    else:
        four = (c0 > c1)[:, None]
        col2 = np.where(four, (2 * col0 + col1) // 3, (col0 + col1) // 2)
        col3 = np.where(four, (col0 + 2 * col1) // 3, (col0 + col1) // 2)
    colors = np.stack([col0, col1, col2, col3], axis=1)
    index = (bits[:, None] >> (np.arange(16, dtype=np.uint32) * 2)) & 3
    picked = colors[np.arange(len(blocks))[:, None], index]
    block_w, block_h = 1920 // 4, 1080 // 4
    count = min(len(picked), block_w * block_h)
    tiled = np.zeros((block_h, block_w, 4, 4, 3), dtype=np.uint8)
    flat = tiled.reshape(block_h * block_w, 4, 4, 3)
    flat[:count] = picked[:count].reshape(count, 4, 4, 3).astype(np.uint8)
    return tiled.transpose(0, 2, 1, 3, 4).reshape(1080, 1920, 3)


def main():
    row = next(row for row in csv.DictReader(open(LIST, encoding="utf-8")) if row["name"] == NAME)
    pages = [page for _pos, page in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
    blocks = dxt_blocks(b"".join(pages[1:]))
    for mode in ("opaque", "fill"):
        image = decode(blocks, mode)
        dest = os.path.join(OUT_DIR, f"_{mode}_{NAME}.png")
        Image.fromarray(image, "RGB").save(dest, compress_level=1)
        print(dest)


if __name__ == "__main__":
    main()
