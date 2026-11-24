# -*- coding: utf-8 -*-
import os
import struct
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
KEY = bytes.fromhex("8d452e")
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"


def apply(data):
    out = bytearray(len(data))
    for i, value in enumerate(data):
        mixed = SEED[i % len(SEED)] ^ KEY[i % len(KEY)]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def main():
    for name in os.listdir(ROOT):
        if name.startswith("063ef5069026cebd"):
            data = open(os.path.join(ROOT, name), "rb").read()
            break
    plain = apply(data)
    obj = zlib.decompressobj()
    page = obj.decompress(plain[4:]) + obj.flush()
    at = page.find(b"DDS ")
    print("page", len(page), "dds", at, "unused", len(obj.unused_data))
    hdr = page[at:at + 128]
    size, flags, height, width, pitch, depth, mips = struct.unpack_from("<7I", hdr, 4)
    fourcc = hdr[84:88]
    print("dds", width, height, "mips", mips, "flags", hex(flags), "fourcc", fourcc)
    print(page[:at + 16].hex())


if __name__ == "__main__":
    main()
