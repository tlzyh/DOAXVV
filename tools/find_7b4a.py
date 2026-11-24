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
    text = text_va = None
    for i in range(nsec):
        base = off + i * 40
        name = data[base:base + 8].split(b"\x00", 1)[0]
        vsize, va, rawsize, raw = struct.unpack_from("<IIII", data, base + 8)
        if name == b".text":
            text = data[raw:raw + rawsize]
            text_va = IMAGE + va
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    needle = b"\x4a\x7b"
    start = 0
    shown = 0
    while shown < 12:
        at = text.find(needle, start)
        if at < 0:
            break
        start = at + 1
        window = text[max(0, at - 6):at + 2]
        # immediate in cmp/mov: the two bytes are the last of the insn
        if text[at - 1] not in (0x3D, 0x81, 0xF7, 0x68) and text[at - 2] not in (0x81, 0x3D):
            continue
        va = text_va + at
        blob = text[max(0, at - 8):at + 16]
        print(f"\n{va:#x}")
        for insn in md.disasm(blob, va - 8):
            print(f"  {insn.address:x}: {insn.mnemonic} {insn.op_str}")
            if insn.address > va:
                break
        shown += 1
    print("shown", shown)
    # also dump 0x140122230
    print("\n== 0x140122230")
    raw = text[(0x140122230 - text_va):(0x140122230 - text_va) + 0x40]
    for insn in md.disasm(raw, 0x140122230):
        print(f"  {insn.address:x}: {insn.mnemonic} {insn.op_str}")
        if insn.address > 0x140122250:
            break


if __name__ == "__main__":
    main()
