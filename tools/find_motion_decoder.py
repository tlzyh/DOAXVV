# -*- coding: utf-8 -*-
"""Find code that loads 1e-4f and sign-extends a 20-bit value (shl 12 / sar 12) nearby."""
import re
import struct

from xref_decrypt import EXE, IMAGE, parse_sections

CONSTANTS = {b"\x17\xb7\xd1\x38": "1e-4f", b"\x00\x40\x1c\x46": "10000.0f"}
WINDOW = 0x200


def main():
    data = open(EXE, "rb").read()
    sections = parse_sections(data)
    targets = {}
    for name, va, vsize, raw, rawsize in sections:
        if name != ".rdata":
            continue
        for const, label in CONSTANTS.items():
            for m in re.finditer(re.escape(const), data[raw:raw + rawsize]):
                if m.start() % 4 == 0:
                    targets[IMAGE + va + m.start()] = label
    _n, tva, _vs, traw, trawsize = next(s for s in sections if s[0] == ".text")
    blob = data[traw:traw + trawsize]
    sar12 = [m.start() for m in re.finditer(rb"\xc1[\xf8-\xff]\x0c", blob)]
    hits = []
    # movss / mulss / cvt with rip-relative operand: ... modrm 05/0d/15/1d/25/2d/35/3d + disp32
    for m in re.finditer(rb"\xf3(?:[\x40-\x4f])?\x0f[\x10\x59\x5e\x58]([\x05\x0d\x15\x1d\x25\x2d\x35\x3d])", blob):
        i = m.end()
        rel = struct.unpack_from("<i", blob, i)[0]
        target = IMAGE + tva + i + 4 + rel
        if target in targets:
            near = [s for s in sar12 if abs(s - m.start()) < WINDOW]
            if near:
                hits.append((IMAGE + tva + m.start(), targets[target], len(near)))
    for va, label, n in hits:
        print(f"{va:#x} {label} sar12 nearby x{n}")
    print("total", len(hits))


if __name__ == "__main__":
    main()
