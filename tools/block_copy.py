# -*- coding: utf-8 -*-
"""See if the last block of a row is a copy of some other block."""
import os

import numpy as np
from PIL import Image

from export_bromides import ROOT, decrypt_np, dxt_blocks
from decrypt import iter_pages

# AYA was a clean, non-wrapping file. Hash is in the list; use the png's sibling by decoding again.
# Read key from the csv.
import csv

LIST = r"D:\Projects\YangHui\DOAXVV\tools\_bromide_list.csv"
name = "BROMIDE_AYA_DF_00_A"
row = next(item for item in csv.DictReader(open(LIST, encoding="utf-8")) if item["name"] == name)
pages = [page for _pos, page in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
blocks = dxt_blocks(b"".join(pages[1:]))
print("blocks", len(blocks), blocks.shape)
rows = len(blocks) // 480
grid = blocks[:rows * 480].reshape(rows, 480, 8)
print("rows", rows)
last = grid[:, -1]
first = grid[:, 0]
# exact matches of the last block against the first block of nearby rows
for delta in range(-2, 3):
    src = np.roll(grid[:, 0], delta, axis=0)
    same = np.all(last == src, axis=1).mean()
    print("last == first shifted by block-rows", delta, round(float(same), 4))
# How far is the last block from the block just left of it, versus from the next row's first, in byte Hamming distance.
def ham(a, b):
    return np.not_equal(a, b).sum(axis=1).mean()
print("hamming last vs inner", round(float(ham(last, grid[:, -2])), 2))
print("hamming last vs next first", round(float(ham(last[:-1], grid[1:, 0])), 2))
print("hamming last vs same first", round(float(ham(last, first)), 2))
print("hamming inner vs inner2", round(float(ham(grid[:, -2], grid[:, -3])), 2))
