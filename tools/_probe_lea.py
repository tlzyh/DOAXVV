# -*- coding: utf-8 -*-
"""RIP-relative LEA xrefs to a few exact strings, plus a short disassembly."""
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000
TEXT_RAW = 0x400
TEXT_VA = 0x1000
TEXT_SIZE = 0x324fa00
NEEDLES = (
    b"file_encrypt_key",
    b"resource_list_encrypt",
    b"/resource_data/",
    b"./DX11_data/",
    b"Qqp7eSOMDzvb9YpIgXUYZdIo9RAu7EKb",
    b"X-DOAXVV-Encrypted",
)


def sections(data):
    e = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, e + 6)[0]
    opt = struct.unpack_from("<H", data, e + 20)[0]
    off = e + 24 + opt
    out = []
    for _ in range(nsec):
        name = data[off:off + 8].split(b"\x00", 1)[0]
        vsize, va, rawsize, raw = struct.unpack_from("<IIII", data, off + 8)
        out.append((name, va, raw, rawsize))
        off += 40
    return out


def va_of(secs, file_off):
    for _name, va, raw, rawsize in secs:
        if raw <= file_off < raw + rawsize:
            return IMAGE + va + (file_off - raw)
    return None


def main():
    data = open(EXE, "rb").read()
    secs = sections(data)
    text = data[TEXT_RAW:TEXT_RAW + TEXT_SIZE]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    wanted = {}
    for needle in NEEDLES:
        at = data.find(needle)
        if at < 0:
            print("missing", needle)
            continue
        va = va_of(secs, at)
        wanted[va] = needle.decode()
        print(f"{needle.decode()} file {at:#x} va {va:#x}")
    hits = {va: [] for va in wanted}
    for i in range(len(text) - 7):
        if text[i] not in (0x48, 0x4C) or text[i + 1] != 0x8D:
            continue
        if (text[i + 2] & 0xC7) != 0x05:
            continue
        rel = struct.unpack_from("<i", text, i + 3)[0]
        src = IMAGE + TEXT_VA + i
        dest = src + 7 + rel
        if dest in hits:
            hits[dest].append(src)
    for va, name in wanted.items():
        print(f"\n{name} lea {len(hits[va])}")
        for src in hits[va][:4]:
            blob = data[src - IMAGE - TEXT_VA + TEXT_RAW - 24:src - IMAGE - TEXT_VA + TEXT_RAW + 48]
            for insn in md.disasm(blob, src - 24):
                mark = ">" if insn.address == src else " "
                print(f"  {mark} {insn.address:x}: {insn.mnemonic:8} {insn.op_str}")
                if insn.address > src + 32:
                    break


if __name__ == "__main__":
    main()
