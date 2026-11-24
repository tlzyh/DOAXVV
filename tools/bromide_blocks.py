# -*- coding: utf-8 -*-
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from decrypt import decrypt, iter_pages

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
KEY = bytes.fromhex("0156553e")


def main():
    path = next(os.path.join(ROOT, name) for name in os.listdir(ROOT) if name.startswith("005064dc5768a5f0"))
    pages = [page for _pos, page in iter_pages(decrypt(open(path, "rb").read(), KEY))]
    body = b"".join(pages[1:])
    print("body", len(body), "expect dxt5", 1920 * 1080, "dxt1", 1920 * 1080 // 2)
    # separator ff ff 00 00
    sep = body.count(b"\xff\xff\x00\x00")
    print("ffff0000", sep)
    # show first 8 groups split by that marker
    parts = body.split(b"\xff\xff\x00\x00")
    lens = [len(p) for p in parts[:12]]
    print("split lens", lens, "parts", len(parts))
    print("first part", parts[0][:24].hex())
    print("second", parts[1][:24].hex())
    # header around width
    page = pages[0]
    at = page.find(b"BROMIDE")
    chunk = page[at:at + 160]
    print("from name")
    for i in range(0, 120, 4):
        print(f"  {at+i:04x} {struct.unpack_from('<I', chunk, i)[0]:10d} {chunk[i:i+4].hex()}")


if __name__ == "__main__":
    main()
