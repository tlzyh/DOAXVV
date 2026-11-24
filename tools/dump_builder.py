# -*- coding: utf-8 -*-
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000


def file_off(va):
    return va - IMAGE - 0xC00


def main():
    data = open(EXE, "rb").read()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    start = 0x142DE88A0
    blob = data[file_off(start):file_off(start) + 0x500]
    for insn in md.disasm(blob, start):
        print(f"{insn.address:x}: {insn.mnemonic:8} {insn.op_str}")
        if insn.address > start + 0x280:
            break


if __name__ == "__main__":
    main()
