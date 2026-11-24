# -*- coding: utf-8 -*-
"""Resolve the AES-256 import function and the bytes that fill xmm0/xmm1."""
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000


def file_off(va):
    return va - IMAGE - 0xC00


def resolve_iat(data, va):
    # FF 15 disp32 at va
    off = file_off(va)
    if data[off] != 0xFF or data[off + 1] != 0x15:
        return None
    disp = struct.unpack_from("<i", data, off + 2)[0]
    dest = va + 6 + disp
    # dest is IAT slot; the import name isn't stored there at rest (it's the thunk).
    # Match against the ILT by slot RVA.
    return dest - IMAGE


def load_imports(data):
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    import_rva = struct.unpack_from("<I", data, e_lfanew + 24 + 112 + 8)[0]
    # sections
    nsect = struct.unpack_from("<H", data, e_lfanew + 6)[0]
    szopt = struct.unpack_from("<H", data, e_lfanew + 20)[0]
    sects = []
    off = e_lfanew + 24 + szopt
    for _ in range(nsect):
        vsz, va, rawsz, raw = struct.unpack_from("<IIII", data, off + 8)
        sects.append((va, max(vsz, rawsz), raw))
        off += 40

    def r2o(rva):
        for va, span, raw in sects:
            if va <= rva < va + span:
                return raw + (rva - va)
        return None

    names = {}
    pos = r2o(import_rva)
    while True:
        ilt, _t, _f, name_rva, iat = struct.unpack_from("<IIIII", data, pos)
        if name_rva == 0:
            break
        toff = r2o(ilt or iat)
        index = 0
        while True:
            val = struct.unpack_from("<Q", data, toff)[0]
            if val == 0:
                break
            if not val >> 63:
                noff = r2o(val & 0x7FFFFFFF)
                end = data.find(b"\x00", noff + 2)
                names[iat + index * 8] = data[noff + 2:end].decode("ascii", "replace")
            index += 1
            toff += 8
        pos += 20
    return names


def main():
    data = open(EXE, "rb").read()
    names = load_imports(data)
    for va in (0x1423FF482, 0x142EFD6AC, 0x142EFDC86):
        rva = resolve_iat(data, va)
        print(f"call {va:#x} -> iat {rva:#x} {names.get(rva)}")

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    start = 0x142EFDBA8
    blob = data[file_off(start):file_off(start) + 0x500]
    print("\n===== after importkey =====")
    n = 0
    for insn in md.disasm(blob, start):
        extra = ""
        if "rip" in insn.op_str:
            disp = struct.unpack_from("<i", data, file_off(insn.address) + insn.size - 4)[0]
            target = insn.address + insn.size + disp
            extra = f"  -> {target:#x}"
            if insn.mnemonic == "call" and data[file_off(insn.address)] == 0xFF:
                extra += " " + str(names.get(target - IMAGE))
        print(f"  {insn.address:x}: {insn.mnemonic:8} {insn.op_str}{extra}")
        n += 1
        if n > 120:
            break

    # find callers of 0x142efda80-ish by scanning E8 to a prologue.
    # locate prologue: walk back to int3
    off = file_off(0x142EFDB20)
    while off > 0 and data[off] != 0xCC:
        off -= 1
    while data[off] == 0xCC:
        off += 1
    fn = IMAGE + 0xC00 + (off - 0x400) 
    # file = va - IMAGE - 0xC00, so va = file + IMAGE + 0xC00, but file is raw offset.
    # raw text offset 0x400 = va 0x140001000, so va = IMAGE + 0x1000 + (raw - 0x400)
    fn = IMAGE + 0x1000 + (off - 0x400)
    print("function start", hex(fn), "file", hex(off))


if __name__ == "__main__":
    main()
