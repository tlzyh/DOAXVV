# -*- coding: utf-8 -*-
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000


def main():
    data = open(EXE, "rb").read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    off = pe + 24 + opt
    for i in range(nsec):
        base = off + i * 40
        name = data[base:base + 8].split(b"\x00", 1)[0]
        _vsz, va, rsz, raw = struct.unpack_from("<IIII", data, base + 8)
        if name == b".text":
            text = data[raw:raw + rsz]
            text_va = IMAGE + va
            break
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    start = 0
    real = 0
    while True:
        at = text.find(b"\x4a\x7b", start)
        if at < 0:
            break
        start = at + 1
        va = text_va + at
        for back in range(0, 8):
            blob = text[at - back:at - back + 24]
            for insn in md.disasm(blob, va - back):
                if insn.address > va:
                    break
                if "0x7b4a" in insn.op_str or "7b4a" in insn.op_str.lower():
                    print(f"{insn.address:x}: {insn.mnemonic} {insn.op_str}")
                    real += 1
                break
    print("real", real)


if __name__ == "__main__":
    main()
