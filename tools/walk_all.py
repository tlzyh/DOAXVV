# -*- coding: utf-8 -*-
"""Walk 16-byte-aligned size+zlib records and summarize each chunk."""
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
MAGICS = (b"GT1G", b"_M1G", b"_N1G", b"_A1G", b"_A2G", b"TLSK", b"DDS ", b"RIFF")


def apply(data, key):
    out = bytearray(len(data))
    n = len(SEED)
    k = len(key)
    for i, value in enumerate(data):
        mixed = SEED[i % n] ^ key[i % k]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def find_file(prefix):
    for rel in ("COMMON", "HIGH", os.path.join("DL", "HIGH")):
        folder = os.path.join(ROOT, rel)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if name.startswith(prefix):
                return os.path.join(folder, name)
    raise SystemExit(prefix)


def align(pos):
    return (pos + 15) & ~15


def strings(blob):
    found = []
    cur = bytearray()
    for value in blob:
        if 32 <= value < 127:
            cur.append(value)
        else:
            if len(cur) >= 6:
                found.append(cur.decode("ascii"))
            cur.clear()
            if len(found) >= 8:
                break
    return found


def walk(plain):
    pos = 0
    rows = []
    while pos + 8 <= len(plain) and len(rows) < 40:
        if plain[pos + 4:pos + 6] not in (b"\x78\x9c", b"\x78\xda", b"\x78\x01"):
            # slide to the next 16-byte slot once, then give up if still wrong
            nxt = align(pos + 1)
            if nxt == pos or nxt + 6 > len(plain) or plain[nxt + 4:nxt + 6] not in (b"\x78\x9c", b"\x78\xda", b"\x78\x01"):
                rows.append(("stop", pos, plain[pos:pos + 16].hex()))
                break
            pos = nxt
            continue
        obj = zlib.decompressobj()
        try:
            inflated = obj.decompress(plain[pos + 4:]) + obj.flush()
        except zlib.error as exc:
            rows.append(("bad", pos, str(exc), plain[pos:pos + 12].hex()))
            break
        used = len(plain) - pos - 4 - len(obj.unused_data)
        marks = [magic.decode("ascii", "replace") for magic in MAGICS if magic in inflated[:4096] or inflated.find(magic, 0, 200000) >= 0]
        rows.append((pos, used, len(inflated), inflated[:8], marks, strings(inflated)[:4]))
        pos = align(pos + 4 + used)
    return rows


def main():
    jobs = (
        ("005064dc5768a5f0", "0156553e"),
        ("003a5d9004023993", "0156553e"),
        ("01bae222a50d5175", "0adb01"),
        ("3a25427aceef1907", "02ae6d22"),
    )
    for prefix, key_hex in jobs:
        path = find_file(prefix)
        data = open(path, "rb").read()
        print("\n==", prefix, "raw4", data[4:6].hex(), "size", len(data))
        plain = apply(data, bytes.fromhex(key_hex))
        for row in walk(plain):
            print(" ", row)


if __name__ == "__main__":
    main()
