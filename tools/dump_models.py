# -*- coding: utf-8 -*-
"""Dump the model-like files opened by the live keys and list Misaki names."""
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


def inflate_first(path, key):
    data = open(path, "rb").read()
    plain = apply(data, key)
    inflated = zlib.decompress(plain[4:])
    return data, plain, inflated


def names_of(blob):
    found = []
    cur = bytearray()
    for value in blob:
        if 32 <= value < 127:
            cur.append(value)
        else:
            if len(cur) >= 4 and any(32 < b < 127 and chr(b).isalpha() for b in cur):
                found.append(cur.decode("ascii"))
            cur.clear()
    return found


def main():
    key_d = bytes.fromhex("d655")
    key_s = bytes.fromhex("092ff0")
    key_t = bytes.fromhex("0adb01")
    high = os.path.join(ROOT, "HIGH")
    print("=== HIGH d655 ===")
    for name in os.listdir(high):
        full = os.path.join(high, name)
        head = open(full, "rb").read(6)
        if head[4:6] != bytes.fromhex("9efa") and head[4:6] != bytes.fromhex("9ebc"):
            continue
        try:
            _data, _plain, inflated = inflate_first(full, key_d)
        except zlib.error as exc:
            print(" fail", name[:16], os.path.getsize(full), exc)
            continue
        print(name[:16], os.path.getsize(full), "out", len(inflated), inflated[:24], names_of(inflated)[:8])

    path = None
    for name in os.listdir(high):
        if name.startswith("334152ab2d1b7e45"):
            path = os.path.join(high, name)
    _data, _plain, inflated = inflate_first(path, key_s)
    print("\n=== _S2G ===", len(inflated))
    print(inflated[:128].hex())
    print(names_of(inflated)[:20])
    open(r"D:\Projects\YangHui\DOAXVV\tools\_s2g.bin", "wb").write(inflated)

    # one head model
    for name in os.listdir(high):
        if name.startswith("69c85feb6b8002a6"):
            _data, _plain, inflated = inflate_first(os.path.join(high, name), key_d)
            open(r"D:\Projects\YangHui\DOAXVV\tools\_mdl_els.bin", "wb").write(inflated)
            print("\n=== hea_els ===", len(inflated))
            print(inflated.hex())

    hits = []
    common = os.path.join(ROOT, "COMMON")
    for name in os.listdir(common):
        full = os.path.join(common, name)
        if os.path.getsize(full) < 32 or os.path.getsize(full) > 200000:
            continue
        head = open(full, "rb").read(6)
        if head[4:6] != bytes.fromhex("93ae"):
            continue
        try:
            _data, _plain, inflated = inflate_first(full, key_t)
        except zlib.error:
            continue
        text = " ".join(names_of(inflated)[:12])
        low = text.lower()
        if "mis" in low or "body" in low or "swim" in low:
            hits.append((name[:16], text[:180]))
    print("\n=== mis/body/swim ===", len(hits))
    for row in hits[:40]:
        print(row)


if __name__ == "__main__":
    main()
