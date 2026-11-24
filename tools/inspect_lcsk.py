# -*- coding: utf-8 -*-
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
MAGICS = (b"GT1G", b"_M1G", b"_N1G", b"_A2G", b"TMC\x00", b"DDS ", b"LCSK", b"char_dat", b"n_hara", b"Bip01")


def apply(data, key):
    out = bytearray(len(data))
    for i, value in enumerate(data):
        mixed = SEED[i % len(SEED)] ^ key[i % len(key)]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def strings(blob):
    found = []
    cur = bytearray()
    for value in blob:
        if 32 <= value < 127:
            cur.append(value)
        else:
            if len(cur) >= 6 and sum(chr(b).isalnum() or chr(b) in "_/" for b in cur) >= len(cur) - 1:
                found.append(cur.decode("ascii"))
            cur.clear()
    return found


def pages(plain):
    pos = 0
    out = []
    while pos + 8 <= len(plain) and len(out) < 6:
        if plain[pos + 4:pos + 6] not in (b"\x78\x9c", b"\x78\xda"):
            nxt = (pos + 16) & ~15
            if nxt == pos or plain[nxt + 4:nxt + 6] not in (b"\x78\x9c", b"\x78\xda"):
                break
            pos = nxt
            continue
        obj = zlib.decompressobj()
        try:
            inflated = obj.decompress(plain[pos + 4:]) + obj.flush()
        except zlib.error:
            break
        used = len(plain) - pos - 4 - len(obj.unused_data)
        out.append(inflated)
        pos = (pos + 4 + used + 15) & ~15
    return out


def main():
    jobs = (
        (bytes.fromhex("a505"), bytes.fromhex("02edaa")),
        (bytes.fromhex("7801"), bytes.fromhex("30ae")),
        (bytes.fromhex("5848"), bytes.fromhex("10e7")),
    )
    for pair, key in jobs:
        print("\n====", pair.hex(), key.hex())
        shown = 0
        for name in os.listdir(ROOT):
            full = os.path.join(ROOT, name)
            size = os.path.getsize(full)
            head = open(full, "rb").read(6)
            if head[4:6] != pair:
                continue
            plain = apply(open(full, "rb").read(), key)
            chunks = pages(plain)
            names = []
            marks = []
            for chunk in chunks:
                names.extend(strings(chunk)[:8])
                marks.extend(magic.decode("latin1") for magic in MAGICS if magic in chunk)
            print(name[:16], "size", size, "pages", len(chunks), "pagelen", [len(c) for c in chunks[:4]], "magic", marks[:6], "names", names[:8])
            shown += 1
            if shown >= 6:
                break


if __name__ == "__main__":
    main()
