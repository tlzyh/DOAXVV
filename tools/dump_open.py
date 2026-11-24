# -*- coding: utf-8 -*-
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000


def file_off(data, va):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    off = pe + 24 + opt
    rva = va - IMAGE
    for i in range(nsec):
        base = off + i * 40
        vsz, sva, rsz, raw = struct.unpack_from("<IIII", data, base + 8)
        if sva <= rva < sva + max(vsz, rsz):
            return raw + (rva - sva)
    raise SystemExit(hex(va))


def dump(data, md, va, size, title):
    print(f"\n===== {title} {va:#x} =====")
    off = file_off(data, va)
    for insn in md.disasm(data[off:off + size], va):
        extra = ""
        if insn.mnemonic == "lea" and "rip" in insn.op_str:
            raw = data[file_off(data, insn.address):file_off(data, insn.address) + insn.size]
            disp = struct.unpack_from("<i", raw, insn.size - 4)[0]
            target = insn.address + insn.size + disp
            extra = f" ; {target:#x}"
        print(f"{insn.address:x}: {insn.mnemonic:8} {insn.op_str}{extra}")
        if insn.mnemonic == "ret" and insn.address > va + 0x10:
            break


def main():
    data = open(EXE, "rb").read()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    dump(data, md, 0x142EE5E70, 0x180, "register path")
    dump(data, md, 0x142EE54D0, 0x200, "walk 0x400 records")


if __name__ == "__main__":
    main()
