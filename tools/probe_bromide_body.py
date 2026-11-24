# -*- coding: utf-8 -*-
"""Compare image payloads of a few bromide names."""
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from export_bromides import ROOT, decrypt_np, image_info
from decrypt import iter_pages

LIST = r"D:\Projects\YangHui\DOAXVV\tools\_bromide_list.csv"
WANT = (
    "BROMIDE_OWN_ZA_91_A_LUN",
    "BROMIDE_AYA_DF_00_A",
    "BROMIDE_MIS_ZA_16_A",
    "BROMIDE_4th_half_anniversary",
    "BROMIDE_OWN_ZA_93_A_KNN_CB",
)


def main():
    rows = {row["name"]: row for row in csv.DictReader(open(LIST, encoding="utf-8"))}
    for name in WANT:
        row = rows[name]
        path = os.path.join(ROOT, row["folder"], row["hash"])
        pages = [page for _pos, page in iter_pages(decrypt_np(open(path, "rb").read(), bytes.fromhex(row["key"])))]
        kind, width, height = image_info(pages[0])
        body = b"".join(pages[1:])
        raw = np.frombuffer(body, dtype=np.uint8)
        marker = b"\xff\xff\x00\x00"
        print(name, "pages", len(pages), "kind", kind, f"{width}x{height}", "body", len(body))
        print(" head", body[:32].hex())
        print(" marker", body.count(marker), "unique", len(set(body[:4096])), "zero", int((raw[:4096] == 0).sum()))
        marker_u8 = np.array([0xFF, 0xFF, 0x00, 0x00], dtype=np.uint8)
        best = (0, 0, 0)
        for shift in range(16):
            span = raw[shift:]
            n = len(span) // 16
            if n < 100:
                continue
            view = span[:n * 16].reshape(n, 16)
            for at in range(13):
                hit = float(np.all(view[:, at:at + 4] == marker_u8, axis=1).mean())
                if hit > best[0]:
                    best = (hit, shift, at)
        print(" best marker", "ratio", round(best[0], 4), "shift", best[1], "at", best[2])


if __name__ == "__main__":
    main()
