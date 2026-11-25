# -*- coding: utf-8 -*-
"""See whether black specks are DXT1 punch-through or a bad block layout."""
import csv
import os

import numpy as np

from export_bromides import LIST, ROOT, dxt_blocks, decrypt_np, image_info
from decrypt import iter_pages

NAMES = (
    "BROMIDE_EVENT_NYO_2025_zy_84_a",
    "BROMIDE_MIS_ZA_16_A",
    "BROMIDE_OWN_ZA_91_A_LUN",
    "BROMIDE_AYA_DF_00_A",
)


def load(name, rows):
    row = rows[name]
    pages = [page for _pos, page in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
    body = b"".join(pages[1:])
    raw = np.frombuffer(body, dtype=np.uint8)
    blocks = dxt_blocks(body).astype(np.uint32)
    c0 = blocks[:, 0] | (blocks[:, 1] << 8)
    c1 = blocks[:, 2] | (blocks[:, 3] << 8)
    bits = blocks[:, 4] | (blocks[:, 5] << 8) | (blocks[:, 6] << 16) | (blocks[:, 7] << 24)
    index = (bits[:, None] >> (np.arange(16, dtype=np.uint32) * 2)) & 3
    three = c0 <= c1
    punch = three[:, None] & (index == 3)
    print(name)
    print("  blocks", len(blocks), "three-color", int(three.sum()), "punch pixels", int(punch.sum()), "punch blocks", int((punch.any(axis=1)).sum()))
    # Where does the chosen decoder put the marker, and how zero is the pad?
    marker = np.array([255, 255, 0, 0], dtype=np.uint8)
    best = None
    for shift in range(16):
        span = raw[shift:]
        count = len(span) // 16
        view = span[: count * 16].reshape(count, 16)
        for at in range(13):
            ratio = float(np.all(view[:, at:at + 4] == marker, axis=1).mean())
            if ratio < 0.99:
                continue
            dxt_index = np.arange(at - 8, at) % 16
            used = np.zeros(16, dtype=bool)
            used[dxt_index] = True
            used[at:at + 4] = True
            pad = view[:, np.flatnonzero(~used)]
            pad_zero = float((pad == 0).mean())
            score = (ratio, pad_zero)
            if best is None or score > best[0]:
                best = (score, shift, at, pad_zero, int((pad != 0).any(axis=1).sum()))
    print("  layout", "shift", best[1], "marker_at", best[2], "pad_zero", round(best[3], 4), "nonzero_pad_blocks", best[4])


def main():
    rows = {row["name"]: row for row in csv.DictReader(open(LIST, encoding="utf-8"))}
    for name in NAMES:
        load(name, rows)


if __name__ == "__main__":
    main()
