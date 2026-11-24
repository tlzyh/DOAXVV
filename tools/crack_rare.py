# -*- coding: utf-8 -*-
"""Crack HIGH files whose cipher pair is too rare for the group search."""
import collections
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"
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


def strings(blob):
    found = []
    cur = bytearray()
    for value in blob[:4000]:
        if 32 <= value < 127:
            cur.append(value)
        else:
            if len(cur) >= 5 and any(chr(b).isalpha() for b in cur):
                found.append(cur.decode("ascii"))
            cur.clear()
            if len(found) >= 5:
                break
    return found


def main():
    files = []
    counts = collections.Counter()
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        if size < 64:
            continue
        head = open(full, "rb").read(8)
        if head.startswith(ASF):
            continue
        pair = bytes(head[4:6])
        counts[pair] += 1
        files.append((pair, size, full, head))
    rare = [item for item in files if 1 <= counts[item[0]] <= 7 and item[0] != b"\x4a\x7b"]
    print("rare", len(rare))
    hits = 0
    for pair, size, full, head in rare:
        sample = open(full, "rb").read(min(size, 20000))
        found = None
        for plain5 in (0x9C, 0xDA):
            m4 = mixed_for(pair[0], 0x78)
            m5 = mixed_for(pair[1], plain5)
            if m4 is None or m5 is None:
                continue
            k1 = SEED[4] ^ m4
            k2 = SEED[5] ^ m5
            keys = (bytes((k1, k2)),) + tuple(bytes((b0, k1, k2)) for b0 in range(256))
            for key in keys:
                short = apply_n(sample, key, 40)
                if short[4] != 0x78 or short[5] != plain5:
                    continue
                try:
                    zlib.decompress(short[4:])
                    good = True
                except zlib.error as exc:
                    good = "incomplete" in str(exc) or "truncated" in str(exc)
                if not good:
                    continue
                try:
                    inflated = zlib.decompress(apply_n(sample, key, min(len(sample), 20000))[4:])
                except zlib.error:
                    continue
                found = (key, inflated)
                break
            if found:
                break
        if not found:
            continue
        key, inflated = found
        hits += 1
        print("HIT", os.path.basename(full)[:16], size, key.hex(), inflated[:8], strings(inflated))
        if hits >= 25:
            break
    print("hits", hits)


if __name__ == "__main__":
    main()
