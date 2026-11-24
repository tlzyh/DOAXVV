# -*- coding: utf-8 -*-
"""Recover a shared archive key from files that share ciphertext bytes 4-5."""
import collections
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
ASF = bytes.fromhex("3026b2758e66cf11")


def mixed_for(cipher, plain):
    if cipher == 0:
        return None if plain else 0
    if plain == cipher:
        return 0
    return cipher ^ plain


def inflate_ok(data, key):
    out = bytearray(data)
    n = len(SEED)
    k = len(key)
    for i, value in enumerate(out):
        mixed = SEED[i % n] ^ key[i % k]
        if value != 0 and value != mixed:
            out[i] = value ^ mixed
    if out[4:6] not in (b"\x78\x9c", b"\x78\xda"):
        return None
    try:
        inflated = zlib.decompress(bytes(out[4:]))
    except zlib.error:
        return None
    if len(inflated) < 16:
        return None
    return inflated[:16]


def main():
    groups = collections.defaultdict(list)
    for rel in ("COMMON", "HIGH"):
        folder = os.path.join(ROOT, rel)
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            size = os.path.getsize(full)
            if size < 256:
                continue
            with open(full, "rb") as handle:
                head = handle.read(8)
            if head.startswith(ASF):
                continue
            groups[(rel, head[4:6])].append((size, full, head[:4]))
    big = []
    for key, rows in groups.items():
        prefixes = {item[2] for item in rows}
        if len(rows) >= 8 and len(prefixes) >= 4:
            big.append((len(rows), key, rows))
    big.sort(reverse=True)
    print("candidate groups", len(big))
    for count, key, _rows in big[:15]:
        print(count, key[0], key[1].hex())
    found = []
    for count, (rel, pair), rows in big:
        cipher4, cipher5 = pair
        m4 = mixed_for(cipher4, 0x78)
        m5 = mixed_for(cipher5, 0x9C)
        if m4 is None or m5 is None:
            continue
        sample = open(rows[0][1], "rb").read(min(rows[0][0], 32768))
        # keylen 2 is fully determined; keylen 3 leaves key[0] free.
        k1 = SEED[4] ^ m4
        k2 = SEED[5] ^ m5
        trials = [(bytes((k1, k2)),), (bytes((k2, k1)),)]
        trials.append(tuple(bytes((b0, k1, k2)) for b0 in range(256)))
        hit = None
        for key in (bytes((k1, k2)),):
            hit = inflate_ok(sample, key)
            if hit:
                found.append((rel, pair.hex(), key.hex(), count, hit))
                print("HIT2", found[-1])
                break
        if hit:
            continue
        for b0 in range(256):
            key = bytes((b0, k1, k2))
            hit = inflate_ok(sample, key)
            if hit:
                found.append((rel, pair.hex(), key.hex(), count, hit))
                print("HIT3", found[-1])
                break
        if len(found) >= 12:
            break
    print("done", len(found))


if __name__ == "__main__":
    main()
