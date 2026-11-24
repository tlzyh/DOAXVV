# -*- coding: utf-8 -*-
"""Print swimsuit-sized HIGH meshes (names containing za or body)."""
import collections
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"


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
    for value in blob[:6000]:
        if 32 <= value < 127:
            cur.append(value)
        else:
            if len(cur) >= 4 and any(chr(b).isalpha() for b in cur):
                found.append(cur.decode("ascii"))
            cur.clear()
            if len(found) >= 4:
                break
    return found


def main():
    counts = collections.Counter()
    files = []
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        if not (20000 <= size <= 250000):
            continue
        head = open(full, "rb").read(6)
        if head[4:6] == b"\x4a\x7b":
            continue
        counts[bytes(head[4:6])] += 1
        files.append((bytes(head[4:6]), size, name, full))
    print("candidates", len(files))
    for pair, size, name, full in files:
        if counts[pair] > 7:
            continue
        sample = open(full, "rb").read(min(size, 12000))
        found = None
        for plain5 in (0x9C,):
            m4 = mixed_for(pair[0], 0x78)
            m5 = mixed_for(pair[1], plain5)
            if m4 is None or m5 is None:
                continue
            k1 = SEED[4] ^ m4
            k2 = SEED[5] ^ m5
            for key in (bytes((k1, k2)),) + tuple(bytes((b0, k1, k2)) for b0 in range(256)):
                short = apply_n(sample, key, 24)
                if short[4] != 0x78 or short[5] != plain5:
                    continue
                try:
                    inflated = zlib.decompress(apply_n(sample, key, len(sample))[4:])
                except zlib.error as exc:
                    if "incomplete" not in str(exc) and "truncated" not in str(exc):
                        continue
                    continue
                found = inflated
                break
        if not found or not found.startswith(b"TMC"):
            continue
        names = strings(found)
        label = " ".join(names)
        low = label.lower()
        if "za_" in low or "mis" in low or "wgt_body" in low or "mizugi" in low:
            print(size, name[:16], label)


if __name__ == "__main__":
    main()
