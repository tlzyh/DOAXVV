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
    page = pages[0]
    print("pages", len(pages), "lens", {len(p) for p in pages})
    # plausible image sizes
    want = {512, 640, 720, 768, 800, 960, 1024, 1080, 1280, 1440, 1536, 1600, 1920, 2048}
    hits = []
    for i in range(0, min(len(page), 4096) - 4, 2):
        value = struct.unpack_from("<I", page, i)[0]
        if value in want:
            hits.append((i, value))
        half = struct.unpack_from("<H", page, i)[0]
        if half in want and half > 256:
            hits.append((i, half, "u16"))
    print("sizes", hits[:40])
    # name and following 256 bytes
    at = page.find(b"BROMIDE")
    print("name at", hex(at))
    print(page[at:at + 128].hex())
    # how page1 differs from a raw image: count unique bytes, look for 8-byte repeat
    p1 = pages[1]
    print("page1 unique", len(set(p1)))
    print("page2 head", pages[2][:32].hex())
    print("last head", pages[-1][:32].hex(), "len", len(pages[-1]))


if __name__ == "__main__":
    main()
