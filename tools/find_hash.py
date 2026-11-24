# -*- coding: utf-8 -*-
"""Find where a known content hash is referenced."""
import os

NEEDLE = bytes.fromhex("01bae222a50d5175a154a530e2a82095")
TEXT = b"01bae222a50d5175"
EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
PKG = (
    r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
    r"\4be7efcc93f64e14d7bd7984ef6eeb2ef5ad802ea74cf12ad50a4d39bab71798"
)


def scan(path, needles):
    data = open(path, "rb").read()
    print(os.path.basename(path), len(data))
    for needle in needles:
        pos = 0
        found = 0
        while found < 5:
            at = data.find(needle, pos)
            if at < 0:
                break
            print(f"  {needle[:8].hex()} at {at:#x}")
            pos = at + 1
            found += 1
        if not found:
            print("  miss", needle[:8])


def main():
    scan(EXE, (NEEDLE, TEXT))
    scan(PKG, (NEEDLE, TEXT))
    # one 80-byte record
    folder = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
    shown = 0
    for name in os.listdir(folder):
        full = os.path.join(folder, name)
        if os.path.getsize(full) == 80:
            print("rec80", name[:16], open(full, "rb").read().hex())
            shown += 1
            if shown >= 2:
                break


if __name__ == "__main__":
    main()
