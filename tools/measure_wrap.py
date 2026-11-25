# -*- coding: utf-8 -*-
"""Measure the right-edge wrap and whether rows are a different stride."""
import csv
import os

import numpy as np
from PIL import Image

from export_bromides import LIST, OUT_DIR, ROOT, decrypt_np, image_info
from decrypt import iter_pages

NAME = "BROMIDE_EVENT_NNM_2024_zy_65_b"


def main():
    image = np.array(Image.open(os.path.join(OUT_DIR, NAME + ".png")).convert("RGB"))
    height, width, _ = image.shape
    print("png", width, height)
    # How many right-hand columns repeat the left edge?
    for span in (4, 8, 12, 16, 20, 24, 32, 48, 64):
        right = image[:, width - span:].astype(int)
        left = image[:, :span].astype(int)
        print("span", span, "right-vs-left mean", np.abs(right - left).mean())
    # Does a horizontal roll make the right strip continue the left scene edge?
    row = image[400].astype(int)
    for shift in range(1, 33):
        rolled = np.roll(image, shift, axis=1)
        # seam energy at x=0 after moving the strip back to the left
        seam = np.abs(rolled[:, 0].astype(int) - rolled[:, -1].astype(int)).mean()
        print("roll", shift, "edge seam", round(seam, 2))

    row = {r["name"]: r for r in csv.DictReader(open(LIST, encoding="utf-8"))}[NAME]
    pages = [page for _pos, page in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
    page = pages[0]
    end = page.find(b"\x00", 0x8C)
    print("header", page[end:end + 80].hex())
    body = b"".join(pages[1:])
    raw = np.frombuffer(body, dtype=np.uint8)
    print("body", len(body), "pages", len(pages), [len(p) for p in pages[:3]], len(pages[-1]))
    marker = np.array([255, 255, 0, 0], dtype=np.uint8)
    for shift in range(16):
        span = raw[shift:]
        count = len(span) // 16
        view = span[:count * 16].reshape(count, 16)
        hits = [int(at) for at in range(13) if np.all(view[:, at:at + 4] == marker, axis=1).mean() > 0.99]
        if hits:
            print("shift", shift, "marker at", hits, "records", count)


if __name__ == "__main__":
    main()
