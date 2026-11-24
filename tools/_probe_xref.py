# -*- coding: utf-8 -*-
"""Find LEA xrefs to a file offset and disassemble the hits."""
import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000
TEXT_RAW = 0x400
TEXT_VA = 0x1000
TEXT_END = 0x324fe00


def va_of(file_off):
    if TEXT_RAW <= file_off < TEXT_END:
        return IMAGE + TEXT_VA + (file_off - TEXT_RAW)
    # .rdata raw 0x324fe00 va 0x3251000
    if 0x324fe00 <= file_off < 0x39b1600:
        return IMAGE + 0x3251000 + (file_off - 0x324fe00)
    raise ValueError(hex(file_off))


def file_off(va):
    rva = va - IMAGE
    if TEXT_VA <= rva < TEXT_VA + (TEXT_END - TEXT_RAW):
        return TEXT_RAW + (rva - TEXT_VA)
    if 0x3251000 <= rva < 0x39b3000:
        return 0x324fe00 + (rva - 0x3251000)
    return None


def find_xrefs(data, target_va):
    text = data[TEXT_RAW:TEXT_END]
    hits = []
    # lea r?, [rip+disp] is 48 8d 05/0d/15/1d/25/2d/35/3d  or 4c 8d
    i = 0
    while i + 7 < len(text):
        b0 = text[i]
        b1 = text[i + 1]
        b2 = text[i + 2]
        if b0 in (0x48, 0x4C) and b1 == 0x8D and (b2 & 0xC7) == 0x05:
            disp = struct.unpack_from("<i", text, i + 3)[0]
            insn_va = IMAGE + TEXT_VA + i
            dest = insn_va + 7 + disp
            if dest == target_va:
                hits.append(insn_va)
            i += 7
            continue
        i += 1
    return hits


def disasm(data, va, count=40):
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    blob = data[file_off(va):file_off(va) + 0x120]
    n = 0
    for insn in md.disasm(blob, va):
        print(f"    {insn.address:x}: {insn.mnemonic:8} {insn.op_str}")
        n += 1
        if n >= count:
            break


def main():
    data = open(EXE, "rb").read()
    needle = sys.argv[1].encode() if len(sys.argv) > 1 else b"./DX11_data/"
    start = 0
    while True:
        index = data.find(needle, start)
        if index < 0:
            break
        start = index + 1
        try:
            target = va_of(index)
        except ValueError:
            print("skip", hex(index))
            continue
        hits = find_xrefs(data, target)
        ctx = data[index:index + 40]
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in ctx)
        print(f"\n{needle!r} file {index:#x} va {target:#x} xrefs {len(hits)} {asc}")
        for hit in hits[:4]:
            print(f"  xref {hit:#x}")
            disasm(data, hit - 0x20, 25)


if __name__ == "__main__":
    main()
