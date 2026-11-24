# -*- coding: utf-8 -*-
"""Dump the function that calls the skip-zero decrypt."""
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000
TARGET = 0x140104541


def main():
    data = open(EXE, "rb").read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    magic = struct.unpack_from("<H", data, pe + 24)[0]
    if magic != 0x20B:
        raise SystemExit(f"magic {magic:#x}")
    dd = pe + 24 + 112
    rva, size = struct.unpack_from("<II", data, dd + 3 * 8)
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    sec_off = pe + 24 + opt
    sections = []
    for i in range(nsec):
        off = sec_off + i * 40
        name = data[off:off + 8].split(b"\x00", 1)[0]
        vsize, va, rawsize, raw = struct.unpack_from("<IIII", data, off + 8)
        sections.append((name, va, vsize, raw, rawsize))

    def file_off(rva_):
        for _name, va, vsize, raw, rawsize in sections:
            if va <= rva_ < va + max(vsize, rawsize):
                return raw + (rva_ - va)
        raise KeyError(hex(rva_))

    pdata = file_off(rva)
    count = size // 12
    target = TARGET - IMAGE
    lo, hi = 0, count
    begin = end = None
    while lo < hi:
        mid = (lo + hi) // 2
        b, e, _u = struct.unpack_from("<III", data, pdata + mid * 12)
        if target < b:
            hi = mid
        elif target >= e:
            lo = mid + 1
        else:
            begin, end = b, e
            break
    print("func", hex(IMAGE + begin), hex(IMAGE + end), "size", end - begin)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    out = open(r"D:\Projects\YangHui\DOAXVV\tools\_reader.txt", "w", encoding="utf-8")
    blob = data[file_off(begin):file_off(end)]
    for insn in md.disasm(blob, IMAGE + begin):
        out.write(f"{insn.address:x}: {insn.mnemonic:8} {insn.op_str}\n")
    print("wrote", end - begin)


if __name__ == "__main__":
    main()
