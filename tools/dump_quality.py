# -*- coding: utf-8 -*-
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000
START = 0x142EE6000


def file_off(data, va):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    off = pe + 24 + opt
    rva = va - IMAGE
    for i in range(nsec):
        base = off + i * 40
        vsz, sva, rsz, raw = struct.unpack_from("<IIII", data, base + 8)
        if sva <= rva < sva + max(vsz, rsz):
            return raw + (rva - sva)
    raise SystemExit(hex(va))


def main():
    data = open(EXE, "rb").read()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    off = file_off(data, START)
    blob = data[off:off + 0x250]
    for insn in md.disasm(blob, START):
        extra = ""
        raw = data[file_off(data, insn.address):file_off(data, insn.address) + insn.size]
        if insn.mnemonic == "lea" and "rip" in insn.op_str:
            disp = struct.unpack_from("<i", raw, insn.size - 4)[0]
            target = insn.address + insn.size + disp
            extra = f" ; {target:#x}"
            pos = file_off(data, target)
            snippet = data[pos:pos + 40]
            if all(32 <= b < 127 or b == 0 for b in snippet[:12]):
                extra += " " + snippet.split(b"\x00", 1)[0].decode("ascii", "replace")
        print(f"{insn.address:x}: {insn.mnemonic:8} {insn.op_str}{extra}")


if __name__ == "__main__":
    main()
