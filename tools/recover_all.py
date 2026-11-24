# -*- coding: utf-8 -*-
"""Recover every shared 2- or 3-byte key that yields a real first chunk."""
import collections
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
ASF = bytes.fromhex("3026b2758e66cf11")


def mixed_for(cipher, plain):
    if cipher == 0:
        return None if plain else 0
    return 0 if plain == cipher else cipher ^ plain


def apply_n(data, key, count):
    out = bytearray(count)
    n = len(SEED)
    k = len(key)
    for i in range(count):
        value = data[i]
        mixed = SEED[i % n] ^ key[i % k]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def opens(data, key):
    short = apply_n(data, key, 48)
    if short[4] != 0x78 or short[5] not in (0x9C, 0xDA):
        return None
    try:
        zlib.decompress(short[4:])
    except zlib.error as exc:
        if "incomplete" not in str(exc) and "truncated" not in str(exc):
            return None
    plain = apply_n(data, key, min(len(data), 20000))
    try:
        inflated = zlib.decompress(plain[4:])
    except zlib.error:
        return None
    return inflated[:16]


def main():
    groups = collections.defaultdict(list)
    for rel in ("COMMON", "HIGH", os.path.join("DL", "COMMON"), os.path.join("DL", "HIGH")):
        folder = os.path.join(ROOT, rel)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size < 64:
                continue
            with open(full, "rb") as handle:
                head = handle.read(8)
            if head.startswith(ASF):
                continue
            groups[(rel, bytes(head[4:6]))].append(full)
    hits = []
    ordered = sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)
    for (rel, pair), paths in ordered:
        if len(paths) < 8:
            continue
        sample = open(paths[0], "rb").read(20000)
        found = None
        for plain5 in (0x9C, 0xDA):
            m4 = mixed_for(pair[0], 0x78)
            m5 = mixed_for(pair[1], plain5)
            if m4 is None or m5 is None:
                continue
            k1 = SEED[4] ^ m4
            k2 = SEED[5] ^ m5
            for key in (bytes((k1, k2)), *(bytes((b0, k1, k2)) for b0 in range(256))):
                got = opens(sample, key)
                if got:
                    found = (key, got)
                    break
            if found:
                break
        if not found:
            continue
        key, got = found
        hits.append((rel, pair.hex(), key.hex(), len(paths), got[:12]))
        print("HIT", hits[-1])
    print("total", len(hits))


if __name__ == "__main__":
    main()
