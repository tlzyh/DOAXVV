# -*- coding: utf-8 -*-
"""Full disassembly of the crypto helpers just before CryptDecrypt."""
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000


def file_off(va):
    return va - IMAGE - 0xC00


def dump(data, va, count, title):
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    blob = data[file_off(va):file_off(va) + 0x400]
    print(f"\n===== {title} {va:#x} =====")
    n = 0
    for insn in md.disasm(blob, va):
        print(f"  {insn.address:x}: {insn.mnemonic:8} {insn.op_str}")
        n += 1
        if n >= count or insn.mnemonic == "int3":
            break


def main():
    data = open(EXE, "rb").read()
    dump(data, 0x1423FF3F0, 80, "helper before decrypt A")
    dump(data, 0x1423FF200, 90, "encrypt/decrypt A body")
    dump(data, 0x142EFD800, 40, "genkey area")
    dump(data, 0x142EFDB20, 80, "importkey / decrypt B")


if __name__ == "__main__":
    main()
