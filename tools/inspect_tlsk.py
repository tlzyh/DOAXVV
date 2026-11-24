# -*- coding: utf-8 -*-
"""Decrypt one confirmed file and describe the chunk layout."""
import glob
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
KEY = bytes.fromhex("0adb01")
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"


def stream(key):
    if not key:
        return SEED
    size = len(SEED) * len(key) // __import__("math").gcd(len(SEED), len(key))
    raw = bytearray(size)
    for i in range(size):
        raw[i] = SEED[i % len(SEED)] ^ key[i % len(key)]
    return bytes(raw)


KS = stream(KEY)


def apply(data, phase=0):
    out = bytearray(len(data))
    n = len(KS)
    for i, value in enumerate(data):
        mixed = KS[(phase + i) % n]
        if value == 0 or value == mixed:
            out[i] = value
        else:
            out[i] = value ^ mixed
    return bytes(out)


def walk(plain):
    pos = 0
    chunks = []
    while pos + 8 <= len(plain) and len(chunks) < 8:
        size = int.from_bytes(plain[pos:pos + 4], "little")
        nxt = plain[pos + 4:pos + 6]
        if nxt not in (b"\x78\x9c", b"\x78\xda", b"\x78\x01"):
            chunks.append(("bad", pos, size, nxt.hex()))
            break
        comp = plain[pos + 4:pos + 4 + size] if 8 <= size <= len(plain) - pos else plain[pos + 4:]
        try:
            inflated = zlib.decompress(comp)
            used = len(comp)
            # trim to the real zlib end
            obj = zlib.decompressobj()
            inflated = obj.decompress(comp)
            inflated += obj.flush()
            used = len(comp) - len(obj.unused_data)
        except zlib.error as exc:
            chunks.append(("zlib", pos, size, str(exc)))
            break
        chunks.append(("ok", pos, size, used, len(inflated), inflated[:16]))
        pos += 4 + used
    return chunks


def strings(blob, limit=24):
    out = []
    cur = bytearray()
    start = 0
    for i, value in enumerate(blob):
        if 32 <= value < 127:
            if not cur:
                start = i
            cur.append(value)
        else:
            if len(cur) >= 6:
                out.append((start, cur.decode("ascii")))
            cur.clear()
        if len(out) >= limit:
            break
    return out


def main():
    path = glob.glob(os.path.join(ROOT, "COMMON", "01bae222a50d5175*"))[0]
    data = open(path, "rb").read()
    plain = apply(data)
    print("file", os.path.basename(path), "size", len(data))
    print("plain head", plain[:48].hex())
    print("chunks", walk(plain))
    obj = zlib.decompressobj()
    inflated = obj.decompress(plain[4:]) + obj.flush()
    print("inflate", len(inflated), "unused", len(obj.unused_data))
    print("strings", strings(inflated))
    open(r"D:\Projects\YangHui\DOAXVV\tools\_sample_tlsk.bin", "wb").write(inflated)

    big = []
    for folder in ("COMMON", "HIGH"):
        folder_path = os.path.join(ROOT, folder)
        for name in os.listdir(folder_path):
            full = os.path.join(folder_path, name)
            size = os.path.getsize(full)
            if size >= 2_000_000:
                big.append((size, folder, full))
            if len(big) >= 4:
                break
        if len(big) >= 4:
            break
    keys = [bytes.fromhex(item) for item in ("0adb01", "092ff0", "076a612e", "d655", "02ae6d22", "01abfe", "0156553e", "8d452e")]
    streams = {key.hex(): stream(key) for key in keys}
    for size, folder, full in big:
        head = open(full, "rb").read(128)
        print("\nBIG", folder, os.path.basename(full)[:16], size)
        for key_name, keystream in streams.items():
            out = bytearray(64)
            n = len(keystream)
            for i, value in enumerate(head[:64]):
                mixed = keystream[i % n]
                out[i] = value if value == 0 or value == mixed else value ^ mixed
            mark = out[4:6]
            print(" ", key_name, out[:8].hex(), "z", mark.hex())


if __name__ == "__main__":
    main()
