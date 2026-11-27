# -*- coding: utf-8 -*-
"""List motion-related strings in DOAX_VV.exe and the code that references them."""
import re
import struct
import sys

from xref_decrypt import EXE, IMAGE, parse_sections

PATTERN = re.compile(rb"[\x20-\x7e]{4,}")
WORDS = [w.encode() for w in (sys.argv[1:] or ["char_dat", "motion", "Motion", "anim", "Anim", "_00v", "MOT_", "clip"])]


def main():
    data = open(EXE, "rb").read()
    sections = parse_sections(data)
    strings = {}
    for name, va, vsize, raw, rawsize in sections:
        if name not in (".rdata", ".data"):
            continue
        for m in PATTERN.finditer(data, raw, raw + rawsize):
            if any(w in m.group() for w in WORDS):
                strings[IMAGE + va + m.start() - raw] = m.group()
    text = next(s for s in sections if s[0] == ".text")
    _n, tva, _vs, traw, trawsize = text
    refs = {va: [] for va in strings}
    blob = data[traw:traw + trawsize]
    for m in re.finditer(rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]", blob):
        i = m.start()
        rel = struct.unpack_from("<i", blob, i + 3)[0]
        target = IMAGE + tva + i + 7 + rel
        if target in refs:
            refs[target].append(IMAGE + tva + i)
    for va in sorted(strings):
        if len(strings[va]) > 100:
            continue
        print(f"{va:#x} {strings[va].decode('latin1')!r} refs {[hex(r) for r in refs[va][:6]]}")


if __name__ == "__main__":
    main()
