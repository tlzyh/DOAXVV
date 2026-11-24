# -*- coding: utf-8 -*-
"""Disassemble the function that references a hardcoded hashed path."""
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000
TEXT_RAW = 0x400
TEXT_VA = 0x1000
PDATA_RAW = 0x3C9C600
PDATA_SIZE = 0x17AA00


def main():
    data = open(EXE, "rb").read()
    needle = b"COMMON/4be7efcc93f64e14d7bd7984ef6eeb2ef5ad802ea74cf12ad50a4d39bab71798"
    at = data.find(needle)
    va = IMAGE + 0x3251000 + (at - 0x324FE00)
    print("string", hex(va))
    text = data[TEXT_RAW:TEXT_RAW + 0x324FA00]
    hits = []
    for i in range(len(text) - 7):
        if text[i] not in (0x48, 0x4C, 0x4D) or text[i + 1] != 0x8D:
            continue
        if (text[i + 2] & 0xC7) != 0x05:
            continue
        rel = struct.unpack_from("<i", text, i + 3)[0]
        src = IMAGE + TEXT_VA + i
        if src + 7 + rel == va:
            hits.append(src)
    print("lea", [hex(h) for h in hits])
    if not hits:
        return
    src = hits[0]
    rva = src - IMAGE
    # binary search pdata
    count = PDATA_SIZE // 12
    lo, hi = 0, count
    begin = end = None
    while lo < hi:
        mid = (lo + hi) // 2
        b, e, _u = struct.unpack_from("<III", data, PDATA_RAW + mid * 12)
        if rva < b:
            hi = mid
        elif rva >= e:
            lo = mid + 1
        else:
            begin, end = b, e
            break
    print("func", hex(IMAGE + begin), hex(IMAGE + end), "size", end - begin)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = False
    blob = data[TEXT_RAW + (begin - TEXT_VA):TEXT_RAW + (end - TEXT_VA)]
    n = 0
    for insn in md.disasm(blob, IMAGE + begin):
        print(f"{insn.address:x}: {insn.mnemonic:8} {insn.op_str}")
        n += 1
        if n > 220:
            print("...")
            break


if __name__ == "__main__":
    main()
