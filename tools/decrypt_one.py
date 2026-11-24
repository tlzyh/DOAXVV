# -*- coding: utf-8 -*-
"""Decrypt one hash file with a live key and report the container."""
import os
import sys
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"


def stream(key):
    size = len(SEED) * len(key) // __import__("math").gcd(len(SEED), len(key))
    raw = bytearray(size)
    for i in range(size):
        raw[i] = SEED[i % len(SEED)] ^ key[i % len(key)]
    return bytes(raw)


def apply(data, keystream):
    out = bytearray(len(data))
    n = len(keystream)
    for i, value in enumerate(data):
        mixed = keystream[i % n]
        if value != 0 and value != mixed:
            out[i] = value ^ mixed
        else:
            out[i] = value
    return bytes(out)


def find_file(prefix):
    for rel in ("COMMON", "HIGH", os.path.join("DL", "COMMON"), os.path.join("DL", "HIGH")):
        folder = os.path.join(ROOT, rel)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if name.startswith(prefix):
                return os.path.join(folder, name)
    raise SystemExit("missing " + prefix)


def strings(blob, limit=30):
    found = []
    cur = bytearray()
    start = 0
    for i, value in enumerate(blob):
        if 32 <= value < 127:
            if not cur:
                start = i
            cur.append(value)
        else:
            if len(cur) >= 5:
                found.append((start, cur.decode("ascii")))
            cur.clear()
            if len(found) >= limit:
                break
    return found


def main():
    prefix = sys.argv[1]
    key = bytes.fromhex(sys.argv[2])
    path = find_file(prefix)
    data = open(path, "rb").read()
    plain = apply(data, stream(key))
    print("file", os.path.basename(path))
    print("size", len(data), "head", plain[:32].hex())
    obj = zlib.decompressobj()
    try:
        inflated = obj.decompress(plain[4:]) + obj.flush()
    except zlib.error as exc:
        print("inflate failed", exc)
        return
    print("inflated", len(inflated), "unused", len(obj.unused_data), "magic", inflated[:16])
    for magic in (b"GT1G", b"_M1G", b"_N1G", b"_A1G", b"_A2G", b"TLSK", b"DDS "):
        print(magic, inflated.find(magic))
    print("strings", strings(inflated, 20))
    out = os.path.join(r"D:\Projects\YangHui\DOAXVV\tools", "_dec_" + prefix[:8] + ".bin")
    open(out, "wb").write(inflated[: min(len(inflated), 4_000_000)])
    print("wrote", out, "bytes", min(len(inflated), 4_000_000))


if __name__ == "__main__":
    main()
