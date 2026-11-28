# -*- coding: utf-8 -*-
"""Disassemble a function of DOAX_VV.exe with string / call annotations.

  python tools\\disasm.py <va hex> [max bytes] [> out.txt]

Starts at the function containing <va> (after the preceding int3 padding) and
stops at max bytes (default 0x1000). RIP-relative operands that point at ASCII
strings are annotated, as are float constants.
"""
import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from xref_decrypt import EXE, parse_sections, file_off

DATA = open(EXE, "rb").read()
SECTIONS = parse_sections(DATA)


def text_at(va):
    try:
        off = file_off(SECTIONS, va)
    except KeyError:
        return None
    raw = DATA[off:off + 120].split(b"\0")[0]
    if len(raw) >= 3 and all(32 <= c < 127 for c in raw):
        return '"%s"' % raw.decode()
    return None


def function_start(va):
    off = file_off(SECTIONS, va)
    while off > 0 and not (DATA[off - 1] == 0xCC and DATA[off - 2] == 0xCC):
        off -= 1
    return va - (file_off(SECTIONS, va) - off)


def disassemble(va, limit=0x1000, from_start=True):
    start = function_start(va) if from_start else va
    off = file_off(SECTIONS, start)
    cs = Cs(CS_ARCH_X86, CS_MODE_64)
    lines = []
    for ins in cs.disasm(DATA[off:off + limit], start):
        line = "%x: %s %s" % (ins.address, ins.mnemonic, ins.op_str)
        if "rip + " in ins.op_str:
            disp = int(ins.op_str.split("rip + ")[1].split("]")[0], 16)
            target = ins.address + ins.size + disp
            note = text_at(target)
            if note is None and "xmm" in ins.op_str:
                try:
                    note = "%g" % struct.unpack_from("<f", DATA, file_off(SECTIONS, target))[0]
                except KeyError:
                    note = None
            line += "   ; %x %s" % (target, note or "")
        lines.append(line)
        if ins.mnemonic == "int3":
            break
    return lines


if __name__ == "__main__":
    target = int(sys.argv[1], 16)
    size = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x1000
    print("\n".join(disassemble(target, size)))
