# -*- coding: utf-8 -*-
"""See which VtxLay integers are exact sizes of the shared HIGH files."""
import os
import struct

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"
TMC = r"D:\Projects\YangHui\DOAXVV\tools\_mis_za.bin"


def main():
    sizes = set()
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        if size < 16:
            continue
        head = open(full, "rb").read(6)
        if head[4:6] == bytes((0x4A, 0x7B)):
            sizes.add(size)
    blob = open(TMC, "rb").read()
    at = blob.find(b"VtxLay\x00")
    window = blob[at:at + 0x90]
    values = [struct.unpack_from("<I", window, i)[0] for i in range(0, len(window) - 3, 4)]
    print("vtx at", hex(at), "pool sizes", len(sizes))
    for value in values:
        mark = ""
        if value in sizes:
            mark = " EXACT"
        elif any(abs(value - size) < 4096 for size in sizes):
            near = min(sizes, key=lambda size: abs(size - value))
            mark = f" near {near} d {value - near}"
        if mark:
            print(f"  {value:10d} {value:#x}{mark}")


if __name__ == "__main__":
    main()
