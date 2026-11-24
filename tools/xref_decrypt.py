# -*- coding: utf-8 -*-
"""Find callers of the skip-zero decrypt and dump the archive vtable."""
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000
DECRYPT = 0x14010FD40
VTABLE = 0x1434BD698


def parse_sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    sec = pe + 24 + opt
    sections = []
    for i in range(nsec):
        off = sec + i * 40
        name = data[off:off + 8].split(b"\x00", 1)[0].decode("ascii", "replace")
        vsize, va, rawsize, raw = struct.unpack_from("<IIII", data, off + 8)
        sections.append((name, va, vsize, raw, rawsize))
    return sections


def file_off(sections, va):
    rva = va - IMAGE
    for _name, sva, vsize, raw, rawsize in sections:
        span = max(vsize, rawsize)
        if sva <= rva < sva + span:
            return raw + (rva - sva)
    raise KeyError(hex(va))


def main():
    data = open(EXE, "rb").read()
    sections = parse_sections(data)
    text = next(item for item in sections if item[0] == ".text")
    _name, sva, vsize, raw, rawsize = text
    blob = data[raw:raw + rawsize]
    hits = []
    for i in range(len(blob) - 5):
        if blob[i] != 0xE8:
            continue
        rel = struct.unpack_from("<i", blob, i + 1)[0]
        src = IMAGE + sva + i
        if src + 5 + rel == DECRYPT:
            hits.append(src)
    print("decrypt callers", [hex(item) for item in hits])
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    for src in hits:
        off = file_off(sections, src - 0x40)
        print(f"\n===== before {src:#x} =====")
        for insn in md.disasm(data[off:off + 0x60], src - 0x40):
            mark = " <==" if insn.address == src else ""
            print(f"  {insn.address:x}: {insn.mnemonic:8} {insn.op_str}{mark}")
            if insn.address > src:
                break
    vt_off = file_off(sections, VTABLE)
    print("\n===== vtable", hex(VTABLE), "=====")
    for i in range(16):
        ptr = struct.unpack_from("<Q", data, vt_off + i * 8)[0]
        print(f"  [{i:2}] {ptr:#x}")


if __name__ == "__main__":
    main()
