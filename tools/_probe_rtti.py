# -*- coding: utf-8 -*-
"""Find a ktgl class vtable from its RTTI name and list the first methods."""
import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000


def sections(data):
    e = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, e + 6)[0]
    opt = struct.unpack_from("<H", data, e + 20)[0]
    off = e + 24 + opt
    out = []
    for _ in range(nsec):
        name = data[off:off + 8].split(b"\x00", 1)[0].decode()
        vsize, va, rawsize, raw = struct.unpack_from("<IIII", data, off + 8)
        out.append((name, va, raw, max(vsize, rawsize)))
        off += 40
    return out


def file_off(secs, rva):
    for _n, va, raw, size in secs:
        if va <= rva < va + size:
            return raw + (rva - va)
    return None


def va_of(secs, off):
    for _n, va, raw, size in secs:
        if raw <= off < raw + size:
            return IMAGE + va + (off - raw)
    return None


def main():
    needle = sys.argv[1].encode()
    data = open(EXE, "rb").read()
    secs = sections(data)
    at = data.find(b".?AV" + needle)
    if at < 0:
        at = data.find(needle)
    print("name file", hex(at))
    td_va = va_of(secs, at) - 16
    td_rva = td_va - IMAGE
    print("td", hex(td_va))
    pat = struct.pack("<I", td_rva)
    cols = []
    start = 0
    while True:
        i = data.find(pat, start)
        if i < 0:
            break
        cols.append(i)
        start = i + 1
    print("col refs", [hex(c) for c in cols])
    # vtable slot -1 is a pointer to the COL. COL starts 12 bytes before the TD rva
    # (signature, offset, cdOffset, pTypeDescriptor). Confirm.
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    for col_td in cols:
        col_off = col_td - 12
        sig = struct.unpack_from("<I", data, col_off)[0]
        col_va = va_of(secs, col_off)
        print("  col", hex(col_va), "sig", hex(sig))
        col_pat = struct.pack("<Q", col_va)
        v = 0
        while True:
            j = data.find(col_pat, v)
            if j < 0:
                break
            vt_va = va_of(secs, j + 8)
            print("  vtable", hex(vt_va), "file", hex(j + 8))
            # print first 8 slots
            for s in range(8):
                fn = struct.unpack_from("<Q", data, j + 8 + s * 8)[0]
                print(f"    [{s}] {fn:#x}")
            # disassemble method 1 and 2 briefly if they look like code
            for s in (1, 2, 3, 4):
                fn = struct.unpack_from("<Q", data, j + 8 + s * 8)[0]
                fr = fn - IMAGE
                fo = file_off(secs, fr)
                if fo is None:
                    continue
                print(f"  -- method {s}")
                blob = data[fo:fo + 160]
                n = 0
                for insn in md.disasm(blob, fn):
                    print(f"    {insn.address:x}: {insn.mnemonic:8} {insn.op_str}")
                    n += 1
                    if n > 25 or insn.mnemonic == "ret":
                        break
            v = j + 1


if __name__ == "__main__":
    main()
