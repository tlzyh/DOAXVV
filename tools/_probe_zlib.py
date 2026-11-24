# -*- coding: utf-8 -*-
"""Check whether 78 9C hits are real zlib, and disassemble model-ish magics."""
import os
import struct
import zlib

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
COMMON = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"


def find_prefix(prefix):
    for name in os.listdir(COMMON):
        if name.startswith(prefix):
            return os.path.join(COMMON, name)
    raise FileNotFoundError(prefix)


def try_zlib(path):
    data = open(path, "rb").read()
    print("size", len(data), "head", data[:32].hex())
    ok = 0
    for sig in (b"\x78\x9c", b"\x78\xda", b"\x78\x01"):
        start = 0
        tried = 0
        while tried < 6:
            index = data.find(sig, start)
            if index < 0:
                break
            tried += 1
            start = index + 1
            for wbits in (15, 31):
                try:
                    out = zlib.decompress(data[index:], wbits)
                except zlib.error:
                    continue
                head = out[:16]
                asc = "".join(chr(b) if 32 <= b < 127 else "." for b in head)
                print(f"  zlib {sig.hex()} @{index:#x} wbits {wbits} out {len(out)} {head.hex()} {asc}")
                ok += 1
                break
    print("real streams", ok)
    png = data.find(b"\x89PNG\r\n\x1a\n")
    print("png", png)


def disasm_at(data, file_off, before=48, after=80):
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    window_off = file_off - before
    window = data[window_off:file_off + after]
    base = 0x140000000 + (window_off - 0x400 + 0x1000)
    print(f"\n---- file {file_off:#x} ----")
    for insn in md.disasm(window, base):
        print(f"  {insn.address:x}: {insn.mnemonic:8} {insn.op_str}")


def main():
    try_zlib(find_prefix("0080aa75ad1a25d7"))
    try_zlib(find_prefix("009f0ca3b19773f1"))
    data = open(EXE, "rb").read()
    for needle in (b"_N1G", b"OC1G", b"9300", b"TexI", b"TLSK", b"_A1G", b"_S2G"):
        index = data.find(needle)
        print(f"\n==== {needle!r} first at {index:#x} ====")
        if 0x400 <= index < 0x324fe00:
            disasm_at(data, index)


if __name__ == "__main__":
    main()
