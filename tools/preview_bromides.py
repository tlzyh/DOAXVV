# -*- coding: utf-8 -*-
import csv
import os

from PIL import Image

from export_bromides import LIST, OUT_DIR, ROOT, decode_file

NAMES = (
    "BROMIDE_AYA_DF_00_A",
    "BROMIDE_MIS_ZA_16_A",
    "BROMIDE_4th_half_anniversary",
    "BROMIDE_OWN_ZA_93_A_KNN_CB",
)


def main():
    rows = {row["name"]: row for row in csv.DictReader(open(LIST, encoding="utf-8"))}
    os.makedirs(OUT_DIR, exist_ok=True)
    for name in NAMES:
        row = rows[name]
        image, width, height, used = decode_file(
            os.path.join(ROOT, row["folder"], row["hash"]), bytes.fromhex(row["key"])
        )
        dest = os.path.join(OUT_DIR, name + ".png")
        Image.fromarray(image, "RGB").save(dest, compress_level=1)
        print(name, width, height, used, dest)


if __name__ == "__main__":
    main()
