# -*- coding: utf-8 -*-
"""Try the 2019 KT XOR scheme against one current COMMON file."""
import os
import struct

COMMON = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
MAGICS = (b"GT1G", b"_M1G", b"_N1G", b"_A2G", b"_A1G", b"_L1G", b"OC1G", b"DDS ", b"RIFF")
SEEDS = [
    bytes.fromhex("4686048e796cd48ad484ec7f6d22a8ea"),
    b"Qqp7eSOMDzvb9YpIgXUYZdIo9RAu7EKb",
    b"Qqp7eSOMDzvb9YpI",
]


def generate_key(num, op):
    if op == "xor":
        a = num ^ 0x3E7
    elif op == "add":
        a = (num + 0x3E7) & 0xFFFFFFFF
    elif op == "sub":
        a = (num - 0x3E7) & 0xFFFFFFFF
    else:
        a = num & 0x3E7
    b = (a * 7) & 0xFFFFFFFF
    c = (b // 0xB) + (num % 0x11) + 0x1AC
    key = []
    for shift in (24, 16, 8, 0):
        val = (c >> shift) & 0xFF
        if val:
            key.append(val)
    return bytes(key) or b"\x00"


def decode(data, seed, file_key, skip):
    mixed = bytes(seed[i] ^ file_key[i % len(file_key)] for i in range(len(seed)))
    out = bytearray(data[:4])
    for i, val in enumerate(data[4:]):
        k = mixed[i % len(mixed)]
        if skip and (val == 0 or val == k):
            out.append(val)
        else:
            out.append(val ^ k)
    return bytes(out)


def main():
    name = None
    for entry in os.listdir(COMMON):
        path = os.path.join(COMMON, entry)
        if 20_000 < os.path.getsize(path) < 40_000:
            head = open(path, "rb").read(4)
            if struct.unpack("<I", head)[0] < 0x10000:
                name = entry
                break
    data = open(os.path.join(COMMON, name), "rb").read(64)
    num = struct.unpack_from("<I", data, 0)[0]
    print("sample", name[:16], "type", hex(num))
    for op in ("xor", "add", "sub", "and"):
        file_key = generate_key(num, op)
        for seed in SEEDS:
            for skip in (True, False):
                out = decode(data, seed, file_key, skip)
                if out[4:8] in MAGICS or out[:4] in MAGICS:
                    print("HIT", op, skip, seed[:8], out[:16])


if __name__ == "__main__":
    main()
