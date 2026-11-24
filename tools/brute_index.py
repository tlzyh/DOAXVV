# -*- coding: utf-8 -*-
"""Map (index * 0x77) // 11 back to the key that opens hash files."""
import glob
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"


def key_of(index):
    dword = (index * 0x77) // 11
    raw = dword.to_bytes(8, "little")
    # The builder keeps only the low 32 bits (mov dword ptr).
    raw = dword & 0xFFFFFFFF
    be = raw.to_bytes(4, "big")
    return bytes(b for b in be if b)


def plain_at(cipher, key, index):
    mixed = SEED[index % len(SEED)]
    if key:
        mixed ^= key[index % len(key)]
    if cipher == 0 or cipher == mixed:
        return cipher
    return cipher ^ mixed


def opens_zlib(head, key):
    if not key:
        return False
    return plain_at(head[4], key, 4) == 0x78 and plain_at(head[5], key, 5) in (0x9C, 0xDA)


def opens_magic(head, key, magic, origin=0):
    for i, want in enumerate(magic):
        if plain_at(head[origin + i], key, origin + i) != want:
            return False
    return True


def main():
    small = open(glob.glob(os.path.join(ROOT, "COMMON", "01bae222a50d5175*"))[0], "rb").read(32)
    print("sample key bytes", key_of(1).hex(), key_of(11).hex(), key_of(12).hex())
    found = []
    for index in range(1, 400000):
        key = key_of(index)
        if key == bytes.fromhex("0adb01"):
            found.append(index)
            if len(found) >= 8:
                break
    print("indexes for 0adb01", found[:8], "count_cap", len(found))
    # confirm the formula actually opens the sample near the first match
    if found:
        key = key_of(found[0])
        print("first", found[0], key.hex(), "zlib", opens_zlib(small, key))

    big_path = None
    for name in os.listdir(os.path.join(ROOT, "COMMON")):
        full = os.path.join(ROOT, "COMMON", name)
        if os.path.getsize(full) > 5_000_000:
            big_path = full
            break
    big = open(big_path, "rb").read(64)
    print("big", os.path.basename(big_path)[:16], "raw", big[:16].hex())
    hits = []
    magics = (b"GT1G", b"_M1G", b"_N1G", b"_A2G", b"_A1G", b"TLSK")
    for index in range(1, 200000):
        key = key_of(index)
        if not key:
            continue
        if opens_zlib(big, key):
            hits.append((index, key.hex(), "zlib+4"))
        else:
            for magic in magics:
                if opens_magic(big, key, magic):
                    hits.append((index, key.hex(), magic.decode()))
                    break
        if len(hits) >= 12:
            break
    print("big hits", hits)

    # How many COMMON files does 0adb01 open?
    key = bytes.fromhex("0adb01")
    ok = 0
    total = 0
    for folder in ("COMMON", "HIGH"):
        folder_path = os.path.join(ROOT, folder)
        for name in os.listdir(folder_path):
            full = os.path.join(folder_path, name)
            size = os.path.getsize(full)
            if size < 16:
                continue
            total += 1
            head = open(full, "rb").read(8)
            if opens_zlib(head, key):
                ok += 1
    print("0adb01 zlib", ok, "of", total)


if __name__ == "__main__":
    main()
