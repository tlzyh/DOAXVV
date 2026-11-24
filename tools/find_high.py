# -*- coding: utf-8 -*-
"""Locate HIGH strings and the code that references them."""
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000


def sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    off = pe + 24 + opt
    out = []
    for i in range(nsec):
        base = off + i * 40
        name = data[base:base + 8].split(b"\x00", 1)[0].decode("ascii", "replace")
        vsz, va, rsz, raw = struct.unpack_from("<IIII", data, base + 8)
        out.append((name, va, vsz, raw, rsz))
    return out


def file_off(secs, va):
    rva = va - IMAGE
    for _name, sva, vsz, raw, rsz in secs:
        if sva <= rva < sva + max(vsz, rsz):
            return raw + (rva - sva)
    raise KeyError(hex(va))


def main():
    data = open(EXE, "rb").read()
    secs = sections(data)
    text = next(item for item in secs if item[0] == ".text")
    _n, text_va, _v, text_raw, text_rsz = text
    text_bytes = data[text_raw:text_raw + text_rsz]
    print("strings")
    start = 0
    sites = []
    while len(sites) < 40:
        at = data.find(b"HIGH", start)
        if at < 0:
            break
        start = at + 1
        window = data[max(0, at - 8):at + 16]
        if not all(32 <= b < 127 or b == 0 for b in window):
            continue
        # map file offset to VA
        va = None
        for name, sva, vsz, raw, rsz in secs:
            if raw <= at < raw + rsz:
                va = IMAGE + sva + (at - raw)
                break
        text_s = window.split(b"\x00", 1)[0]
        sites.append((va, at, text_s))
        print(f"  {va:#x} {text_s!r}" if va else f"  file {at:#x} {text_s!r}")
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    for va, _at, label in sites:
        if va is None:
            continue
        hits = []
        # RIP-relative LEA: opcode 48/4C 8D xx, disp32 at +3, length often 7
        for i in range(len(text_bytes) - 7):
            if text_bytes[i] not in (0x48, 0x4C) or text_bytes[i + 1] != 0x8D:
                continue
            if (text_bytes[i + 2] & 0xC7) != 0x05:
                continue
            disp = struct.unpack_from("<i", text_bytes, i + 3)[0]
            src = IMAGE + text_va + i
            if src + 7 + disp == va:
                hits.append(src)
        print(f"lea {label!r} { [hex(h) for h in hits[:8]] }")
        if not hits:
            continue
        src = hits[0]
        off = file_off(secs, src - 0x20)
        print(f"  around {src:#x}")
        for insn in md.disasm(data[off:off + 0x40], src - 0x20):
            mark = " <==" if insn.address == src else ""
            print(f"    {insn.address:x}: {insn.mnemonic} {insn.op_str}{mark}")
            if insn.address > src + 8:
                break


if __name__ == "__main__":
    main()
