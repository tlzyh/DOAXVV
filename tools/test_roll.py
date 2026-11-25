# -*- coding: utf-8 -*-
"""Find the right-edge seam and test a one-block row rotation."""
import csv
import os

import numpy as np
from PIL import Image

from export_bromides import LIST, ROOT, decrypt_np, dxt_blocks, image_info, rgb565
from decrypt import iter_pages

NAME = "BROMIDE_EVENT_NNM_2024_zy_65_b"
OUT = r"D:\Projects\YangHui\DOAXVV\export\_phase"


def save(name, crop, scale=4):
    image = Image.fromarray(crop).resize((crop.shape[1] * scale, crop.shape[0] * scale), Image.NEAREST)
    image.save(os.path.join(OUT, name))


def indices(bits):
    return (bits[:, None] >> (np.arange(16, dtype=np.uint32) * 2)) & 3


def decode_order(blocks, order):
    raw = blocks.astype(np.uint32)
    c0 = raw[:, 0] | (raw[:, 1] << 8)
    c1 = raw[:, 2] | (raw[:, 3] << 8)
    bits = raw[:, 4] | (raw[:, 5] << 8) | (raw[:, 6] << 16) | (raw[:, 7] << 24)
    col0 = rgb565(c0)
    col1 = rgb565(c1)
    four = (c0 > c1)[:, None]
    col2 = np.where(four, (2 * col0 + col1) // 3, (col0 + col1) // 2)
    col3 = np.where(four, (col0 + 2 * col1) // 3, (col0 + col1) // 2)
    colors = np.stack([col0, col1, col2, col3], axis=1)
    picked = colors[np.arange(len(blocks))[:, None], indices(bits)[:, order]]
    bw, bh = 480, 270
    count = min(len(picked), bw * bh)
    tiled = np.zeros((bh, bw, 4, 4, 3), dtype=np.uint8)
    tiled.reshape(bh * bw, 4, 4, 3)[:count] = picked[:count].reshape(count, 4, 4, 3)
    return tiled.transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 3)


def main():
    im = np.array(Image.open(os.path.join(r"D:\Projects\YangHui\DOAXVV\export\bromide", NAME + ".png")))
    region = im[200:700, -80:]
    jump = np.abs(region[:, 1:].astype(int) - region[:, :-1].astype(int)).mean(axis=(0, 2))
    print("right jumps", [(int(1920 - 80 + i + 1), round(float(v), 2)) for i, v in enumerate(jump)])

    row = {item["name"]: item for item in csv.DictReader(open(LIST, encoding="utf-8"))}[NAME]
    pages = [p for _, p in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
    blocks = dxt_blocks(b"".join(pages[1:]))
    print("blocks", len(blocks), image_info(pages[0]))

    # Move one block column between the ends of every row.
    grid = np.zeros((270, 480, 8), dtype=np.uint8)
    use = min(len(blocks), 270 * 480)
    grid.reshape(270 * 480, 8)[:use] = blocks[:use]
    for name, rolled in (
        ("roll_m1", np.roll(grid, -1, axis=1)),
        ("roll_p1", np.roll(grid, 1, axis=1)),
        ("roll_m2", np.roll(grid, -2, axis=1)),
    ):
        image = decode_order(rolled.reshape(270 * 480, 8), np.arange(16))
        save(name + ".png", image[200:700, -48:])
        # seam between the new join inside the picture, at x=4 or x=1916
        seam = np.abs(image[:, 4].astype(int) - image[:, 3].astype(int)).mean()
        edge = np.abs(image[:, 0].astype(int) - image[:, -1].astype(int)).mean()
        print(name, "inner4", round(float(seam), 2), "outer", round(float(edge), 2))

    # Index orders: standard, x-flipped inside the block, bit-reversed word.
    xflip = np.array([(y * 4 + (3 - x)) for y in range(4) for x in range(4)])
    yflip = np.array([((3 - y) * 4 + x) for y in range(4) for x in range(4)])
    rev = np.arange(15, -1, -1)
    for name, order in (("std", np.arange(16)), ("xflip", xflip), ("yflip", yflip), ("rev", rev)):
        image = decode_order(blocks, order)
        save("ord_" + name + ".png", image[80:360, 250:560], 2)


if __name__ == "__main__":
    main()
