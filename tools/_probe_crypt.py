# -*- coding: utf-8 -*-
"""Locate CryptDecrypt call sites and a skip-if-zero XOR loop."""
import struct

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"


def pe_sections(data):
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    image_base = struct.unpack_from("<Q", data, e_lfanew + 24 + 24)[0]
    nsect = struct.unpack_from("<H", data, e_lfanew + 6)[0]
    szopt = struct.unpack_from("<H", data, e_lfanew + 20)[0]
    sect_off = e_lfanew + 24 + szopt
    sects = []
    for i in range(nsect):
        off = sect_off + i * 40
        name = data[off:off + 8].split(b"\x00", 1)[0].decode("ascii", "replace")
        vsz, va, rawsz, raw = struct.unpack_from("<IIII", data, off + 8)
        sects.append((name, va, vsz, raw, rawsz))
    return image_base, sects


def rva_to_off(sects, rva):
    for name, va, vsz, raw, rawsz in sects:
        span = max(vsz, rawsz)
        if va <= rva < va + span:
            return raw + (rva - va)
    return None


def imports(data, sects):
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    import_rva = struct.unpack_from("<I", data, e_lfanew + 24 + 112 + 8)[0]
    off = rva_to_off(sects, import_rva)
    found = []
    while True:
        ilt, _tds, _fwd, name_rva, iat = struct.unpack_from("<IIIII", data, off)
        if name_rva == 0:
            break
        name_off = rva_to_off(sects, name_rva)
        end = data.find(b"\x00", name_off)
        dll = data[name_off:end].decode("ascii", "replace")
        thunk_rva = ilt or iat
        toff = rva_to_off(sects, thunk_rva)
        index = 0
        while True:
            val = struct.unpack_from("<Q", data, toff)[0]
            if val == 0:
                break
            if not (val >> 63):
                noff = rva_to_off(sects, val & 0x7FFFFFFF)
                end = data.find(b"\x00", noff + 2)
                fn = data[noff + 2:end].decode("ascii", "replace")
                if fn.startswith("Crypt"):
                    found.append((dll, fn, iat + index * 8))
            index += 1
            toff += 8
        off += 20
    return found


def main():
    data = open(EXE, "rb").read()
    image_base, sects = pe_sections(data)
    print("image base", hex(image_base))
    crypt = imports(data, sects)
    for dll, fn, rva in crypt:
        print(f"  {dll} {fn} iat {rva:#x}")
    text_va, text_vsz, text_raw, text_rawsz = None, None, None, None
    for name, va, vsz, raw, rawsz in sects:
        if name == ".text":
            text_va, text_vsz, text_raw, text_rawsz = va, vsz, raw, rawsz
    text = data[text_raw:text_raw + text_rawsz]
    targets = {image_base + rva: fn for _dll, fn, rva in crypt}
    calls = {fn: [] for fn in targets.values()}
    i = 0
    while i + 6 < len(text):
        if text[i] == 0xFF and text[i + 1] == 0x15:
            disp = struct.unpack_from("<i", text, i + 2)[0]
            insn_va = image_base + text_va + i
            dest = insn_va + 6 + disp
            fn = targets.get(dest)
            if fn:
                calls[fn].append(insn_va)
            i += 6
            continue
        i += 1
    for fn, sites in calls.items():
        if sites:
            print(fn, "calls", len(sites), "first", [hex(s) for s in sites[:8]])

    # skip-zero xor: test al,al / jz / cmp al,reg / jz / xor
    hits = []
    sig = b"\x84\xc0"
    start = 0
    while len(hits) < 30:
        j = text.find(sig, start)
        if j < 0 or j + 12 >= len(text):
            break
        start = j + 1
        if text[j + 2] != 0x74:
            continue
        window = text[j:j + 16]
        if b"\x32" in window or b"\x30" in window:
            hits.append(image_base + text_va + j)
    print("xor-skip candidates", len(hits))
    for va in hits[:20]:
        print(" ", hex(va))


if __name__ == "__main__":
    main()
