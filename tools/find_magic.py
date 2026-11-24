# -*- coding: utf-8 -*-
"""Find code that compares against the HIGH container word 0x7B4A."""
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
    text = None
    for i in range(nsec):
        base = off + i * 40
        name = data[base:base + 8].split(b"\x00", 1)[0]
        vsize, va, rawsize, raw = struct.unpack_from("<IIII", data, base + 8)
        if name == b".text":
            text = data[raw:raw + rawsize]
            text_va = IMAGE + va
            break
    needle = b"\x4a\x7b"
    hits = []
    start = 0
    while len(hits) < 40:
        at = text.find(needle, start)
        if at < 0:
            break
        start = at + 1
        # keep only comparisons: previous bytes look like cmp/mov reg, imm16
        prev = text[max(0, at - 4):at]
        if prev[-1:] in (b"\x3d", b"\x81", b"\xf7", b"\xf6") or (len(prev) >= 2 and prev[-2] == 0x66 and prev[-1] in (0x3D, 0x81, 0xF7)):
            hits.append(text_va + at)
        elif b"\x66" in prev and prev[-1] in (0x3D, 0x81, 0xF7, 0x81):
            hits.append(text_va + at)
    print("hits", [hex(h) for h in hits])
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    for va in hits[:8]:
        rel = va - text_va
        blob = text[max(0, rel - 12):rel + 24]
        print(f"\n-- {va:#x}")
        for insn in md.disasm(blob, va - 12):
            print(f"  {insn.address:x}: {insn.mnemonic} {insn.op_str}")


if __name__ == "__main__":
    main()
