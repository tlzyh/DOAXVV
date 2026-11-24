# -*- coding: utf-8 -*-
import hashlib
import os

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
NAMES = ("s_MIS_HAIR_00", "s_MIS_HAIR_01", "s_MIS_ZA_16_A", "hea_els_00_a", "gra_chr_00_a")


def main():
    names = set()
    for rel in ("COMMON", "HIGH"):
        for name in os.listdir(os.path.join(ROOT, rel)):
            names.add(name)
    for text in NAMES:
        variants = [
            text.encode(),
            text.lower().encode(),
            text.upper().encode(),
            (text + "\x00").encode(),
            text.encode("utf-16le"),
        ]
        print(text)
        for blob in variants:
            digest = hashlib.sha256(blob).hexdigest()
            print(" ", blob[:24], digest[:16], "HIT" if digest in names else "")


if __name__ == "__main__":
    main()
