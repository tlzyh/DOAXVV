# -*- coding: utf-8 -*-
"""Find instructions that compare against the word 0x7B4A."""
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
        vsize, va, rawsize, raw = struct.unpack_from("<IIII", data, base + 8)
        if name == b".text":
            text = data[raw:raw + rawsize]
            text_va = IMAGE + va
            break
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    # any 4A 7B whose preceding bytes can be an imm16 operand
    hits = []
    start = 0
    while len(hits) < 30:
        at = text.find(b"\x4a\x7b", start)
        if at < 0:
            break
        start = at + 1
        prev = text[at - 3:at]
        if prev[-1] in (0x3D, 0x81, 0xF7, 0x68) or prev[-2] in (0x81, 0xF7) or (prev[-2] == 0x66 and prev[-1] in (0x3D, 0x81)):
            hits.append(text_va + at)
    print("candidates", [hex(h) for h in hits])
    for va in hits[:8]:
        rel = va - text_va
        blob = text[rel - 12:rel + 20]
        print(f"\n{va:#x}")
        for insn in md.disasm(blob, va - 12):
            print(f"  {insn.address:x}: {insn.mnemonic} {insn.op_str}")


if __name__ == "__main__":
    main()
