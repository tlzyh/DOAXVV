# -*- coding: utf-8 -*-
"""Pull the constant blocks the cipher setup copies, and the code that mixes them."""
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000
BEGIN = 0x142DE6250
END = 0x142DE6B4E


def rdata(data, va):
    return 0x324FE00 + (va - IMAGE - 0x3251000)


def main():
    data = open(EXE, "rb").read()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    blob = data[0x400 + (BEGIN - IMAGE - 0x1000):0x400 + (END - IMAGE - 0x1000)]
    consts = []
    lines = []
    for insn in md.disasm(blob, BEGIN):
        raw = bytes(insn.bytes)
        if insn.mnemonic == "movdqa" and raw[0] == 0x66 and 0x6F in raw[:4]:
            # 66 0F 6F modrm disp32, possibly with a rex between? no, 66 is the prefix
            modrm_at = raw.index(0x6F) + 1
            if raw[modrm_at] == 0x05:
                disp = struct.unpack_from("<i", raw, modrm_at + 1)[0]
                src = insn.address + insn.size + disp
                consts.append(data[rdata(data, src):rdata(data, src) + 16])
                continue
        if insn.mnemonic in ("movdqa", "movaps") and "rbp" in insn.op_str:
            continue
        lines.append(f"{insn.address:x}: {insn.mnemonic:8} {insn.op_str}")
    seed = b"".join(consts)
    open(r"D:\Projects\YangHui\DOAXVV\tools\_seed.bin", "wb").write(seed)
    open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_code.txt", "w").write("\n".join(lines))
    print("blocks", len(consts), "bytes", len(seed))
    print(seed[:80].hex())
    print("code lines", len(lines))


if __name__ == "__main__":
    main()
