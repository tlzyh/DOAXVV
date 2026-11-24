# -*- coding: utf-8 -*-
import os
import struct
import zlib

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
PATH = os.path.join(ROOT, "01b6647fe27d5c29")


def find_full(prefix):
    for name in os.listdir(ROOT):
        if name.startswith(prefix):
            return os.path.join(ROOT, name)
    raise SystemExit(prefix)


def main():
    path = find_full("01b6647fe27d5c29")
    data = open(path, "rb").read(4096)
    print("u32s:")
    for i in range(0, 128, 4):
        print(f"  {i:3} {struct.unpack_from('<I', data, i)[0]:10d} {data[i:i+4].hex()}")
    full = open(path, "rb").read()
    at = full.find(b"\x78\x9c")
    print("zlib at", at, "file", len(full))
    window = full[at - 16:at + 8]
    print("around", window.hex())
    for label, blob in (("raw", full[at:at + 200000]),):
        try:
            out = zlib.decompress(blob)
            print(label, "inflate", len(out), out[:24])
        except zlib.error as exc:
            print(label, exc)
    # also the second file's header u32s already known; count 78 9c
    print("zlib count", full.count(b"\x78\x9c"))


if __name__ == "__main__":
    main()
