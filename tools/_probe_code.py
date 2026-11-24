# -*- coding: utf-8 -*-
"""Disassemble the GT1G / _A2G checks inside DOAX_VV.exe."""
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"


def main():
    data = open(EXE, "rb").read()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = False
    for needle in (b"GT1G", b"_A2G", b"_M1G", b"SM1G", b"GM1G", b"_L1G", b"KOVS"):
        start = 0
        hits = 0
        while hits < 3:
            index = data.find(needle, start)
            if index < 0:
                break
            hits += 1
            print(f"\n==== {needle!r} at file {index:#x} ====")
            window = data[index - 64:index + 96]
            base = 0x140000000 + (index - 64 - 0x400 + 0x1000)
            # only .text uses that mapping; print raw if outside
            if not (0x400 <= index < 0x324fe00):
                print("outside .text", window[:32].hex())
                start = index + 1
                continue
            for insn in md.disasm(window, base):
                mark = " <<" if needle.decode() in insn.op_str or needle.decode() in insn.mnemonic else ""
                print(f"  {insn.address:x}: {insn.mnemonic:8} {insn.op_str}{mark}")
            start = index + 1
        if hits == 0:
            print(needle, "not found")


if __name__ == "__main__":
    main()
