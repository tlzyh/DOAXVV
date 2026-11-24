# -*- coding: utf-8 -*-
"""Inflate the first page of every file a live key actually opens."""
import collections
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
KEYS = [
    bytes.fromhex(item)
    for item in ("0adb01", "0156553e", "092ff0", "076a612e", "d655", "02ae6d22", "01abfe", "8d452e")
]
INTEREST = ("mis", "body", "hair", "swim", "GT1G", "_M1G", "_N1G", "n_hara", "Bip", "g1m", "g1t")


def crypt(value, mixed):
    if value == 0 or value == mixed:
        return value
    return value ^ mixed


def cipher_pair(key, plain):
    out = bytearray()
    for i, value in enumerate(plain):
        index = 4 + i
        mixed = SEED[index % len(SEED)] ^ key[index % len(key)]
        out.append(crypt(value, mixed))
    return bytes(out)


def apply(data, key):
    out = bytearray(len(data))
    for i, value in enumerate(data):
        mixed = SEED[i % len(SEED)] ^ key[i % len(key)]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def first_names(blob):
    names = []
    cur = bytearray()
    for value in blob:
        if 32 <= value < 127:
            cur.append(value)
        else:
            if len(cur) >= 4:
                text = cur.decode("ascii")
                if any(ch.isalpha() for ch in text):
                    names.append(text)
            cur.clear()
            if len(names) >= 6:
                break
    return names


def main():
    pairs = {}
    for key in KEYS:
        for magic in (b"\x78\x9c", b"\x78\xda"):
            pairs.setdefault(cipher_pair(key, magic), []).append((key, magic))
    print("pair map", {k.hex(): [item[0].hex() for item in v] for k, v in pairs.items()})
    counts = collections.Counter()
    interesting = []
    shown = collections.Counter()
    for rel in ("COMMON", "HIGH", os.path.join("DL", "COMMON"), os.path.join("DL", "HIGH")):
        folder = os.path.join(ROOT, rel)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            size = os.path.getsize(full)
            if size < 32:
                continue
            with open(full, "rb") as handle:
                head = handle.read(8192)
            match = pairs.get(head[4:6])
            if not match:
                continue
            key = match[0][0]
            plain = apply(head, key)
            try:
                inflated = zlib.decompress(plain[4:])
            except zlib.error:
                counts[(rel, key.hex(), "fail")] += 1
                continue
            names = first_names(inflated)
            kind = inflated[:4]
            counts[(rel, key.hex(), kind.decode("ascii", "replace"))] += 1
            blob_text = inflated[:4000]
            if any(token.encode("ascii") in blob_text or token in " ".join(names) for token in INTEREST):
                interesting.append((rel, name[:16], size, key.hex(), names[:4]))
            if shown[(rel, key.hex())] < 4:
                shown[(rel, key.hex())] += 1
                print("ex", rel, name[:16], size, key.hex(), names[:3])
    print("--- counts ---")
    for key, count in sorted(counts.items(), key=lambda item: -item[1]):
        print(count, key)
    print("--- interesting", len(interesting), "---")
    for row in interesting[:40]:
        print(row)


if __name__ == "__main__":
    main()
