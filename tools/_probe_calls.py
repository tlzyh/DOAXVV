# -*- coding: utf-8 -*-
"""Disassemble the two CryptDecrypt callers and print referenced strings."""
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000


def file_off(va):
    return va - IMAGE - 0xC00


def main():
    data = open(EXE, "rb").read()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    ranges = [
        (0x1423FEF00, 0x1423FF800, "derive/decrypt A"),
        (0x142EFD200, 0x142EFDF00, "import/decrypt B"),
    ]
    for start, end, title in ranges:
        print(f"\n======== {title} ========")
        blob = data[file_off(start):file_off(end)]
        for insn in md.disasm(blob, start):
            extra = ""
            if insn.mnemonic == "lea" and "rip" in insn.op_str:
                # rip-relative: address is next insn + disp
                disp = struct.unpack_from("<i", data, file_off(insn.address) + insn.size - 4)[0]
                target = insn.address + insn.size + disp
                off = file_off(target)
                if 0 <= off < len(data):
                    raw = data[off:off + 48]
                    if raw and all(32 <= b < 127 or b == 0 for b in raw[:24]):
                        extra = " ; " + raw.split(b"\x00", 1)[0].decode("ascii", "replace")
                    else:
                        extra = " ; " + raw[:16].hex()
            if insn.mnemonic.startswith("call") or extra or "Crypt" in extra:
                print(f"  {insn.address:x}: {insn.mnemonic:8} {insn.op_str}{extra}")


if __name__ == "__main__":
    main()
