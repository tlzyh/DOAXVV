# -*- coding: utf-8 -*-
import csv
import os

import numpy as np
from PIL import Image

from export_bromides import LIST, ROOT, decrypt_np, dxt_blocks, decode_dxt1
from decrypt import iter_pages

OUT = r"D:\Projects\YangHui\DOAXVV\export\_phase"
MARKER = np.array([255, 255, 0, 0], dtype=np.uint8)


def contiguous_blocks(body):
    raw = np.frombuffer(body, dtype=np.uint8)
    best = None
    chosen = None
    for shift in range(16):
        span = raw[shift:]
        count = len(span) // 16
        if count < 16:
            continue
        view = span[:count * 16].reshape(count, 16)
        for at in range(8, 13):
            ratio = float(np.all(view[:, at:at + 4] == MARKER, axis=1).mean())
            if ratio < 0.99:
                continue
            dxt_index = np.arange(at - 8, at)
            used = np.zeros(16, dtype=bool)
            used[dxt_index] = True
            used[at:at + 4] = True
            pad_zero = float((view[:, np.flatnonzero(~used)] == 0).mean())
            score = (ratio, pad_zero)
            if best is None or score > best:
                best = score
                chosen = view[:, dxt_index]
    if chosen is None:
        raise RuntimeError("no contiguous layout")
    return chosen


def settle(blocks):
    rows = len(blocks) // 480
    grid = blocks[:rows * 480].reshape(rows, 480, 8).copy()
    moved = np.empty_like(grid)
    moved[0, 0] = grid[0, 0]
    moved[0, 1:] = grid[0, :-1]
    moved[1:, 0] = grid[:-1, -1]
    moved[1:, 1:] = grid[1:, :-1]
    return moved.reshape(-1, 8)


def show(name, blocks):
    image, _ = decode_dxt1(blocks, 1920, 1080)
    Image.fromarray(image).resize((960, 540), Image.BILINEAR).save(os.path.join(OUT, name + ".jpg"), quality=80)
    crop = image[180:640, 1888:1920]
    Image.fromarray(crop).resize((128, (640 - 180) * 4), Image.NEAREST).save(os.path.join(OUT, name + "_R.png"))


def main():
    rows = {item["name"]: item for item in csv.DictReader(open(LIST, encoding="utf-8"))}
    for name in ("BROMIDE_EVENT_NNM_2024_zy_65_b", "BROMIDE_OWN_ZA_91_A_LUN"):
        row = rows[name]
        pages = [page for _pos, page in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
        blocks = contiguous_blocks(b"".join(pages[1:]))
        show(name[-12:] + "_fix", settle(blocks))
        print(name, "ok")


if __name__ == "__main__":
    main()
