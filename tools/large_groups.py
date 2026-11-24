# -*- coding: utf-8 -*-
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
    for value in blob[:8000]:
        if 32 <= value < 127:
            cur.append(value)
        else:
            if len(cur) >= 4 and any(chr(b).isalpha() for b in cur):
                found.append(cur.decode("ascii"))
            cur.clear()
            if len(found) >= 6:
                break
    return found


def main():
    groups = collections.defaultdict(list)
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        if size < 20000:
            continue
        head = open(full, "rb").read(6)
        if head[4:6] == b"\x4a\x7b":
            continue
        groups[bytes(head[4:6])].append((size, full))
    print("large pairs", len(groups))
    shown = 0
    for pair, rows in sorted(groups.items(), key=lambda item: -len(item[1])):
        if len(rows) < 8:
            continue
        rows.sort(reverse=True)
        size, full = rows[0]
        sample = open(full, "rb").read(min(size, 20000))
        found = None
        for plain5 in (0x9C, 0xDA):
            m4 = mixed_for(pair[0], 0x78)
            m5 = mixed_for(pair[1], plain5)
            if m4 is None or m5 is None:
                continue
            k1 = SEED[4] ^ m4
            k2 = SEED[5] ^ m5
            for key in (bytes((k1, k2)),) + tuple(bytes((b0, k1, k2)) for b0 in range(256)):
                short = apply_n(sample, key, 32)
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
                    inflated = zlib.decompress(apply_n(sample, key, len(sample))[4:])
                except zlib.error:
                    continue
                found = (key, inflated)
                break
            if found:
                break
        if not found:
            print("fail", pair.hex(), "n", len(rows), "max", size)
            continue
        key, inflated = found
        print("OK", pair.hex(), key.hex(), "n", len(rows), "max", size, strings(inflated))
        shown += 1
    print("shown", shown)


if __name__ == "__main__":
    main()
