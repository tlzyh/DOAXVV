# -*- coding: utf-8 -*-
"""Find the skip-zero XOR loop used by the old KT asset cipher."""
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000
TEXT_RAW = 0x400
TEXT_VA = 0x1000
TEXT_SIZE = 0x324FA00


def main():
    data = open(EXE, "rb").read()
    text = data[TEXT_RAW:TEXT_RAW + TEXT_SIZE]
    hits = []
    for i in range(len(text) - 16):
        if text[i] != 0x84 or text[i + 1] != 0xC0 or text[i + 2] != 0x74:
            continue
        # within the next 12 bytes: cmp al + jz + xor al
        window = text[i + 4:i + 18]
        if b"\x32" not in window and b"\x30" not in window:
            continue
        if b"\x3a" not in window and b"\x38" not in window and b"\x3c" not in window:
            continue
        hits.append(i)
    print("candidates", len(hits))
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    shown = 0
    for off in hits:
        va = IMAGE + TEXT_VA + off
        blob = text[off - 16:off + 48]
        lines = []
        for insn in md.disasm(blob, va - 16):
            lines.append(f"{insn.address:x}: {insn.mnemonic:8} {insn.op_str}")
            if insn.address > va + 28:
                break
        text_lines = "\n".join(lines)
        if "xor" not in text_lines:
            continue
        print(f"\n@{va:#x}")
        print(text_lines)
        shown += 1
        if shown >= 12:
            break


if __name__ == "__main__":
    main()
