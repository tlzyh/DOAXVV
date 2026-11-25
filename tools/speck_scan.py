# -*- coding: utf-8 -*-
"""Relate black specks to the 16-byte record phase."""
import csv
import os
from collections import Counter

import numpy as np

from export_bromides import LIST, ROOT, decrypt_np
from decrypt import iter_pages

MARKER = np.array([255, 255, 0, 0], dtype=np.uint8)


def layout_and_punch(body):
    raw = np.frombuffer(body, dtype=np.uint8)
    best = None
    chosen = None
    for shift in range(16):
        span = raw[shift:]
        count = len(span) // 16
        if count < 16:
            continue
        view = span[: count * 16].reshape(count, 16)
        for at in range(13):
            ratio = float(np.all(view[:, at:at + 4] == MARKER, axis=1).mean())
            if ratio < 0.99:
                continue
            dxt_index = np.arange(at - 8, at) % 16
            used = np.zeros(16, dtype=bool)
            used[dxt_index] = True
            used[at:at + 4] = True
            pad_zero = float((view[:, np.flatnonzero(~used)] == 0).mean())
            score = (ratio, pad_zero)
            if best is None or score > best:
                best = score
                chosen = (shift, int(at), view[:, dxt_index])
    shift, at, blocks = chosen
    blocks = blocks.astype(np.uint32)
    c0 = blocks[:, 0] | (blocks[:, 1] << 8)
    c1 = blocks[:, 2] | (blocks[:, 3] << 8)
    bits = blocks[:, 4] | (blocks[:, 5] << 8) | (blocks[:, 6] << 16) | (blocks[:, 7] << 24)
    index = (bits[:, None] >> (np.arange(16, dtype=np.uint32) * 2)) & 3
    punch = int(((c0 <= c1)[:, None] & (index == 3)).sum())
    return shift, at, punch


def main():
    rows = list(csv.DictReader(open(LIST, encoding="utf-8")))
    tally = Counter()
    speckled = []
    for i, row in enumerate(rows, 1):
        pages = [page for _pos, page in iter_pages(decrypt_np(open(os.path.join(ROOT, row["folder"], row["hash"]), "rb").read(), bytes.fromhex(row["key"])))]
        shift, at, punch = layout_and_punch(b"".join(pages[1:]))
        tally[(shift, at, punch > 0)] += 1
        if punch > 1000:
            speckled.append((punch, row["name"], shift, at))
        if i % 200 == 0:
            print("scanned", i, flush=True)
    print("groups", sorted(tally.items()))
    speckled.sort(reverse=True)
    print("speckled", len(speckled))
    print("worst", speckled[:12])


if __name__ == "__main__":
    main()
