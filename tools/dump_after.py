# -*- coding: utf-8 -*-
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
START = 0x142EE3F80


def main():
    data = open(EXE, "rb").read()
    # .text raw 0x400, va 0x1000
    off = 0x400 + (START - 0x140001000)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    n = 0
    for insn in md.disasm(data[off:off + 0x500], START):
        if insn.mnemonic.startswith("call") or insn.mnemonic in ("lea", "jmp") or "0x400" in insn.op_str:
            print(f"{insn.address:x}: {insn.mnemonic:8} {insn.op_str}")
        n += 1
        if insn.mnemonic == "ret" and insn.address > 0x142EE4300:
            break
        if n > 220:
            break


if __name__ == "__main__":
    main()
