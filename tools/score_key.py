# -*- coding: utf-8 -*-
"""Score every 2-byte key against the shared blob by plaintext structure."""
import os
import struct

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"


def load():
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        if os.path.getsize(full) == 2460000:
            return open(full, "rb").read(4096)
    raise SystemExit("missing")


def mixed_options(cipher, plain):
    if cipher == 0:
        return (0,) if plain == 0 else ()
    opts = []
    if plain == cipher:
        opts.append(cipher)
        opts.append(0)
    else:
        mixed = cipher ^ plain
        if mixed != cipher:
            opts.append(mixed)
    return tuple(opts)


def apply(data, key):
    out = bytearray(len(data))
    n = len(SEED)
    k = len(key)
    for i, value in enumerate(data):
        mixed = SEED[i % n] ^ key[i % k]
        if value == 0 or value == mixed:
            out[i] = value
        else:
            out[i] = value ^ mixed
    return bytes(out)


def score(blob):
    zeros = blob.count(0)
    good = 0
    for i in range(0, len(blob) - 4, 4):
        value = struct.unpack_from("<f", blob, i)[0]
        if value == value and abs(value) < 8:
            good += 1
    return zeros + good * 2


def main():
    data = load()
    c4, c5 = data[4], data[5]
    best = []
    # keylen 2: positions 4 and 5 select key[0] and key[1]
    for p4 in range(256):
        for m4 in mixed_options(c4, p4):
            k0 = SEED[4] ^ m4
            for p5 in range(256):
                for m5 in mixed_options(c5, p5):
                    k1 = SEED[5] ^ m5
                    key = bytes((k0, k1))
                    plain = apply(data[:256], key)
                    if plain[:4] == b"TMC\x00" or plain[:4] == b"DDS " or plain[:4] == b"TLSK":
                        print("MAGIC", key.hex(), plain[:8])
                    value = score(plain)
                    best.append((value, key.hex(), plain[:8].hex()))
    best.sort(reverse=True)
    print("top", best[:8], "worst", best[-1][0])


if __name__ == "__main__":
    main()
