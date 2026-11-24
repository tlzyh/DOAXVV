# -*- coding: utf-8 -*-
"""Walk successive zlib streams inside a decrypted hash file."""
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"


def apply(data, key):
    out = bytearray(len(data))
    for i, value in enumerate(data):
        mixed = SEED[i % len(SEED)] ^ key[i % len(key)]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def find_file(prefix):
    for rel in ("COMMON", "HIGH"):
        folder = os.path.join(ROOT, rel)
        for name in os.listdir(folder):
            if name.startswith(prefix):
                return os.path.join(folder, name)
    raise SystemExit(prefix)


def walk(plain):
    pos = 0
    chunks = []
    while pos + 8 <= len(plain) and len(chunks) < 12:
        size = int.from_bytes(plain[pos:pos + 4], "little")
        if plain[pos + 4:pos + 6] not in (b"\x78\x9c", b"\x78\xda", b"\x78\x01"):
            chunks.append(("stop", pos, plain[pos:pos + 16].hex()))
            break
        obj = zlib.decompressobj()
        try:
            inflated = obj.decompress(plain[pos + 4:]) + obj.flush()
        except zlib.error as exc:
            chunks.append(("bad", pos, size, str(exc)))
            break
        used = len(plain) - pos - 4 - len(obj.unused_data)
        chunks.append((pos, size, used, len(inflated), inflated[:12]))
        pos += 4 + used
    return chunks


def main():
    key = bytes.fromhex("0156553e")
    for prefix in ("005064dc5768a5f0", "003a5d9004023993", "01bae222a50d5175"):
        path = find_file(prefix)
        data = open(path, "rb").read()
        plain = apply(data, key if prefix != "01bae222a50d5175" else bytes.fromhex("0adb01"))
        print("\n", prefix, len(data))
        print(walk(plain))


if __name__ == "__main__":
    main()
