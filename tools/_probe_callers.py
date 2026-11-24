# -*- coding: utf-8 -*-
"""Find direct calls into the G1T / G1N parsers."""
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000
TEXT_RAW = 0x400
TEXT_VA = 0x1000
TEXT_SIZE = 0x324fa00


def file_off(va):
    return TEXT_RAW + (va - IMAGE - TEXT_VA)


def main():
    data = open(EXE, "rb").read()
    text = data[TEXT_RAW:TEXT_RAW + TEXT_SIZE]
    # function starts observed just after int3 padding
    targets = {
        0x142FB9120: "g1t",
    }
    # find _N1G function start
    n1 = data.find(b"_N1G")
    # the cmp immediate is inside the function; walk back to CC padding
    off = n1
    while data[off] != 0xCC:
        off -= 1
    while data[off] == 0xCC:
        off += 1
    n1_va = IMAGE + TEXT_VA + (off - TEXT_RAW)
    targets[n1_va] = "g1n"
    print("g1n start", hex(n1_va))
    hits = {name: [] for name in targets.values()}
    i = 0
    while i + 5 < len(text):
        if text[i] == 0xE8:
            rel = struct.unpack_from("<i", text, i + 1)[0]
            src = IMAGE + TEXT_VA + i
            dest = src + 5 + rel
            name = targets.get(dest)
            if name:
                hits[name].append(src)
            i += 5
            continue
        i += 1
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    for name, sites in hits.items():
        print(name, "callers", len(sites))
        for src in sites[:6]:
            print(f"  from {src:#x}")
            blob = data[file_off(src) - 0x40:file_off(src) + 0x20]
            n = 0
            for insn in md.disasm(blob, src - 0x40):
                if insn.address >= src - 0x30:
                    print(f"    {insn.address:x}: {insn.mnemonic:8} {insn.op_str}")
                n += 1


if __name__ == "__main__":
    main()
