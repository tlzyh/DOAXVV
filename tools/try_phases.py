# -*- coding: utf-8 -*-
"""Try each marker phase and see which one is sharp and unwrapped."""
import csv
import os

import numpy as np
from PIL import Image

from export_bromides import LIST, ROOT, decrypt_np, decode_dxt1, image_info
from decrypt import iter_pages

NAME = "BROMIDE_EVENT_NNM_2024_zy_65_b"
MARKER = np.array([255, 255, 0, 0], dtype=np.uint8)
OUT = r"D:\Projects\YangHui\DOAXVV\export\_phase"


def main():
    row = {item["name"]: item for item in csv.DictReader(open(LIST, encoding="utf-8"))}[NAME]
    pages = [page for _pos, page in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
    body = b"".join(pages[1:])
    raw = np.frombuffer(body, dtype=np.uint8)
    os.makedirs(OUT, exist_ok=True)
    kind, width, height = image_info(pages[0])
    # Column discontinuity of the current png.
    current = np.array(Image.open(os.path.join(r"D:\Projects\YangHui\DOAXVV\export\bromide", NAME + ".png")))
    jump = np.abs(current[:, 1:].astype(int) - current[:, :-1].astype(int)).mean(axis=(0, 2))
    top = np.argsort(jump)[-8:]
    print("biggest column jumps", [(int(i + 1), round(float(jump[i]), 2)) for i in top])

    for shift in range(16):
        span = raw[shift:]
        count = len(span) // 16
        view = span[:count * 16].reshape(count, 16)
        for at in range(13):
            if float(np.all(view[:, at:at + 4] == MARKER, axis=1).mean()) < 0.99:
                continue
            dxt_index = np.arange(at - 8, at) % 16
            used = np.zeros(16, dtype=bool)
            used[dxt_index] = True
            used[at:at + 4] = True
            pad = view[:, np.flatnonzero(~used)]
            pad_zero = float((pad == 0).mean())
            wraps = bool(dxt_index[0] > dxt_index[-1])
            image, used_blocks = decode_dxt1(view[:, dxt_index], width, height)
            jump = np.abs(image[:, 1:].astype(int) - image[:, :-1].astype(int)).mean()
            dest = os.path.join(OUT, f"s{shift}_at{at}.png")
            Image.fromarray(image, "RGB").save(dest, compress_level=1)
            print(f"shift {shift:2} at {at:2} pad0 {pad_zero:.3f} wrap {wraps} jump {jump:.3f} blocks {used_blocks}")


if __name__ == "__main__":
    main()
