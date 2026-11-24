# -*- coding: utf-8 -*-
"""Decrypt a bromide and write a PNG from its 4x4 blocks."""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(__file__))
from decrypt import decrypt, iter_pages

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
OUT = r"D:\Projects\YangHui\DOAXVV\export\BROMIDE_OWN_ZA_91_A_LUN.png"
KEY = bytes.fromhex("0156553e")
PREFIX = "005064dc5768a5f0"
BLOCK_W = 1920 // 4


def rgb565(value):
    red = ((value >> 11) & 31) * 255 // 31
    green = ((value >> 5) & 63) * 255 // 63
    blue = (value & 31) * 255 // 31
    return red, green, blue


def decode_dxt1(block, pixels, width, x0, y0):
    c0, c1 = struct.unpack_from("<HH", block, 0)
    bits = struct.unpack_from("<I", block, 4)[0]
    colors = [rgb565(c0), rgb565(c1)]
    if c0 > c1:
        colors.append(tuple((2 * a + b) // 3 for a, b in zip(colors[0], colors[1])))
        colors.append(tuple((a + 2 * b) // 3 for a, b in zip(colors[0], colors[1])))
    else:
        colors.append(tuple((a + b) // 2 for a, b in zip(colors[0], colors[1])))
        colors.append((0, 0, 0))
    for y in range(4):
        for x in range(4):
            idx = (bits >> (2 * (y * 4 + x))) & 3
            px = x0 + x
            py = y0 + y
            if px < width and py * width + px < len(pixels):
                pixels[py * width + px] = colors[idx]


def write_png(path, width, height, pixels):
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixels[y * width + x])
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    open(path, "wb").write(png)


def main():
    path = next(os.path.join(ROOT, name) for name in os.listdir(ROOT) if name.startswith(PREFIX))
    pages = [page for _pos, page in iter_pages(decrypt(open(path, "rb").read(), KEY))]
    body = b"".join(pages[1:])
    blocks = len(body) // 16
    rows = (blocks + BLOCK_W - 1) // BLOCK_W
    width = BLOCK_W * 4
    height = rows * 4
    pixels = [(0, 0, 0)] * (width * height)
    for i in range(blocks):
        block = body[i * 16 + 4:i * 16 + 12]
        decode_dxt1(block, pixels, width, (i % BLOCK_W) * 4, (i // BLOCK_W) * 4)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    write_png(OUT, width, height, pixels)
    print("pages", len(pages), "blocks", blocks, "png", width, height)
    print(OUT)


if __name__ == "__main__":
    main()
