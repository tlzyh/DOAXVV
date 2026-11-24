# -*- coding: utf-8 -*-
"""Scan code for ASCII fourcc compares, and large files for known magics."""
import os
import struct

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
COMMON = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
NEEDLES = [
    b"GT1G", b"_M1G", b"_A2G", b"SM1G", b"GM1G", b"DDS ", b"RIFF",
    b"PNG", b"OggS", b"KOVS", b"\x78\x9c", b"\x78\xda", b"\x78\x01",
    b"IDRK", b"_DRK",
]


def fourcc_ok(value):
    raw = struct.pack("<I", value)
    return all(32 <= b < 127 for b in raw)


def scan_code():
    data = open(EXE, "rb").read()
    text = data[0x400:0x324fe00]
    found = {}
    i = 0
    n = len(text)
    while i + 6 < n:
        op = text[i]
        imm = None
        if op == 0x3D and i + 5 <= n:
            imm = struct.unpack_from("<I", text, i + 1)[0]
        elif op == 0x81 and i + 6 <= n:
            modrm = text[i + 1]
            reg = (modrm >> 3) & 7
            if reg == 7:
                mod = modrm >> 6
                rm = modrm & 7
                pos = i + 2
                if rm == 4 and mod != 3:
                    pos += 1
                if mod == 1:
                    pos += 1
                elif mod == 2:
                    pos += 4
                if pos + 4 <= n:
                    imm = struct.unpack_from("<I", text, pos)[0]
        if imm is not None and fourcc_ok(imm):
            raw = struct.pack("<I", imm)
            found.setdefault(raw, 0)
            found[raw] += 1
        i += 1
    items = sorted(found.items(), key=lambda kv: -kv[1])
    print("fourcc compares", len(items))
    for raw, count in items[:80]:
        print(f"  {count:4} {raw!r}")


def scan_files():
    print("--- large files ---")
    shown = 0
    for name in os.listdir(COMMON):
        path = os.path.join(COMMON, name)
        size = os.path.getsize(path)
        if size < 1_000_000 or size > 8_000_000:
            continue
        blob = open(path, "rb").read(16)
        if blob[:4] in (b"_L1G", b"0&\xb2u") or blob[:4] == bytes.fromhex("3026b275"):
            continue
        data = open(path, "rb").read()
        hits = []
        for needle in NEEDLES:
            count = data.count(needle)
            if count:
                hits.append((needle, count, data.find(needle)))
        print(name[:20], size, "head", data[:24].hex(), "hits", hits[:8])
        shown += 1
        if shown >= 8:
            break


if __name__ == "__main__":
    scan_code()
    scan_files()
