# -*- coding: utf-8 -*-
"""Try alternate keystream phases and the 'header byte is the key byte' case."""
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"
MAGICS = (b"TMC\x00", b"TLSK", b"GT1G", b"_M1G", b"_N1G", b"_A2G", b"DDS ", b"CONTE", b"clip", b"_S2G")


def load():
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        if os.path.getsize(full) < 4096:
            continue
        head = open(full, "rb").read(6)
        if head[4:6] == b"\x4a\x7b":
            return open(full, "rb").read(65536)
    raise SystemExit("none")


def apply(data, key, origin):
    out = bytearray(len(data))
    n = len(SEED)
    k = len(key) if key else 1
    for i, value in enumerate(data):
        mixed = SEED[(origin + i) % n]
        if key:
            mixed ^= key[(origin + i) % k]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def describe(label, plain):
    marks = [magic for magic in MAGICS if magic in plain[:256]]
    zpos = plain.find(b"\x78\x9c", 0, 64)
    inflated = None
    if zpos >= 0:
        try:
            inflated = zlib.decompress(plain[zpos:])[:12]
        except zlib.error:
            inflated = None
    if marks or inflated:
        print("HIT", label, marks, zpos, inflated, plain[:16].hex())


def main():
    sample = load()
    print("sample", sample[:8].hex())
    # header bytes are the key bytes (left unchanged by the cipher)
    for origin in (0, 4):
        describe(f"key4a7b origin{origin}", apply(sample, b"\x4a\x7b", origin))
        for b0 in range(256):
            key = bytes((b0, 0x4A, 0x7B))
            plain = apply(sample[:128], key, origin)
            marks = [magic for magic in MAGICS if magic in plain[:64]]
            if b"\x78\x9c" in plain[:24] or b"\x78\xda" in plain[:24] or marks:
                describe(f"k3 {key.hex()} origin{origin}", apply(sample, key, origin))
    # zlib at offset 4, but keystream restarts there
    print("restart search")
    for plain0, plain1 in ((0x78, 0x9C), (0x78, 0xDA)):
        # file byte 4 uses seed[0]
        m4 = sample[4] ^ plain0
        m5 = sample[5] ^ plain1
        k0 = SEED[0] ^ m4
        k1 = SEED[1] ^ m5
        for key in (bytes((k0, k1)),):
            describe(f"restart2 {key.hex()} {plain0:02x}{plain1:02x}", apply(sample, key, 4))
        for b0 in (0, k0):
            key = bytes((b0, k0, k1)) if False else None
        for b0 in range(256):
            key = bytes((b0, k0, k1))
            blob = apply(sample[:40], key, 4)
            if blob[4:6] != bytes((plain0, plain1)):
                continue
            try:
                inflated = zlib.decompress(blob[4:])
            except zlib.error as exc:
                if "incomplete" not in str(exc) and "truncated" not in str(exc):
                    continue
                try:
                    inflated = zlib.decompress(apply(sample, key, 4)[4:])
                except zlib.error:
                    continue
            print("RESTART HIT", key.hex(), inflated[:16])
            return
    print("done")


if __name__ == "__main__":
    main()
