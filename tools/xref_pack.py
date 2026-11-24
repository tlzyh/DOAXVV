# -*- coding: utf-8 -*-
"""Disassemble the code that references the COMMON/HIGH/LOW package paths."""
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000
TARGETS = {
    0x143478800: "COMMON",
    0x143478850: "HIGH",
    0x1434788A0: "LOW",
}


def main():
    data = open(EXE, "rb").read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    off = pe + 24 + opt
    text = None
    for i in range(nsec):
        base = off + i * 40
        name = data[base:base + 8].split(b"\x00", 1)[0]
        vsz, va, rsz, raw = struct.unpack_from("<IIII", data, base + 8)
        if name == b".text":
            text = data[raw:raw + rsz]
            text_va = IMAGE + va
            text_raw = raw
    hits = {key: [] for key in TARGETS}
    for i in range(len(text) - 7):
        if text[i] not in (0x48, 0x4C) or text[i + 1] != 0x8D:
            continue
        if (text[i + 2] & 0xC7) != 0x05:
            continue
        disp = struct.unpack_from("<i", text, i + 3)[0]
        src = text_va + i
        dest = src + 7 + disp
        if dest in hits:
            hits[dest].append(src)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    for dest, label in TARGETS.items():
        print(label, [hex(item) for item in hits[dest]])
    # disassemble a window around the first HIGH reference, and a bit of the function
    src = hits[0x143478850][0]
    blob_off = text_raw + (src - text_va) - 0x80
    print(f"\naround HIGH lea {src:#x}")
    for insn in md.disasm(data[blob_off:blob_off + 0x120], src - 0x80):
        mark = " <==" if insn.address == src else ""
        print(f"  {insn.address:x}: {insn.mnemonic:8} {insn.op_str}{mark}")


if __name__ == "__main__":
    main()
