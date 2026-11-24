# -*- coding: utf-8 -*-
"""Find large bromide TLSK files among the 4-byte-key archives."""
import collections
import csv
import os
import struct
import sys
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from decrypt import SEED

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
INDEX = r"D:\Projects\YangHui\DOAXVV\index.csv"
OUT = r"D:\Projects\YangHui\DOAXVV\tools\_bromide_list.csv"
SEED_U8 = np.frombuffer(SEED, dtype=np.uint8)
PROBE = 64
COMMON_LAST = [0x3E, 0x5F, 0x7F, 0x13, 0x34, 0x29, 0xAB, 0xB5, 0x8A, 0x08, 0x95, 0x54]


def cstr(blob, at):
    end = blob.find(b"\x00", at)
    if end < 0:
        end = min(len(blob), at + 80)
    return blob[at:end].decode("ascii", "replace")


def promising(blob):
    try:
        zlib.decompress(blob)
        return True
    except zlib.error as exc:
        text = str(exc)
        return "incomplete" in text or "truncated" in text


def decrypt_into(data, key):
    src = np.frombuffer(data, dtype=np.uint8)
    idx = np.arange(len(src))
    key_u8 = np.frombuffer(key, dtype=np.uint8)
    mixed = SEED_U8[idx % len(SEED_U8)] ^ key_u8[idx % len(key_u8)]
    out = np.bitwise_xor(src, mixed)
    keep = (src == 0) | (src == mixed)
    out[keep] = src[keep]
    return out.tobytes()


def probe_family(data, b2):
    n = min(PROBE, len(data))
    idx = np.arange(n)
    seed = SEED_U8[idx % len(SEED_U8)]
    lasts = np.arange(256, dtype=np.uint8)
    keymat = np.empty((256, n), dtype=np.uint8)
    keymat[:, 0::4] = 0x01
    keymat[:, 1::4] = 0x56
    keymat[:, 2::4] = b2
    keymat[:, 3::4] = lasts[:, None]
    mixed = seed[None, :] ^ keymat
    src = np.frombuffer(data[:n], dtype=np.uint8)[None, :]
    out = np.where((src == 0) | (src == mixed), src, src ^ mixed)
    return out


def confirm(data, key):
    plain = decrypt_into(data, key)
    try:
        return zlib.decompress(plain[4:])
    except zlib.error:
        return None


def open_file(data, full_brute):
    order = COMMON_LAST + [i for i in range(256) if i not in set(COMMON_LAST)]
    families = [0x55, 0x54]
    if full_brute:
        families += [b2 for b2 in range(256) if b2 not in (0x55, 0x54)]
    for b2 in families:
        probed = probe_family(data, b2)
        for last in order:
            if not promising(bytes(probed[last, 4:])):
                continue
            key = bytes((0x01, 0x56, b2, last))
            page = confirm(data, key)
            if page and page.startswith(b"TLSK"):
                return key, page
    return None, None


def header_fields(page):
    end = page.find(b"\x00", 0x8C)
    name = page[0x8C:end].decode("ascii", "replace")
    pos = end + 1
    kind = struct.unpack_from("<I", page, pos)[0]
    width, height = struct.unpack_from("<HH", page, pos + 4)
    pixels, pitch = struct.unpack_from("<II", page, pos + 28)
    return name, width, height, pixels, pitch, kind


def main():
    rows = []
    pair_sizes = collections.Counter()
    for row in csv.DictReader(open(INDEX, encoding="utf-8")):
        if row["magic"]:
            continue
        pair_sizes[(row["cipher_pair"], int(row["size"]) // 100000)] += 1
        if row["cipher_pair"] == "49f9":
            rows.append(row)
    print("49f9", len(rows))
    big = [(pair, bucket, n) for (pair, bucket), n in pair_sizes.items() if bucket >= 5 and n >= 20]
    print("other large unknown clusters", sorted(big, key=lambda item: -item[2])[:15])

    found = []
    missed = []
    prefixes = collections.Counter()
    for index, row in enumerate(rows, 1):
        path = os.path.join(ROOT, row["folder"], row["hash"])
        size = int(row["size"])
        data = open(path, "rb").read(min(size, 65536))
        key, page = open_file(data, size >= 100000)
        if page is None:
            missed.append(row["hash"][:16])
            continue
        name, width, height, pixels, pitch, kind = header_fields(page)
        prefixes[name.split("_", 1)[0]] += 1
        if prefixes[name.split("_", 1)[0]] <= 3:
            print(" sample", name, width, height, kind, flush=True)
        if name.startswith("BROMIDE"):
            found.append((row["folder"], row["hash"], row["size"], key.hex(), name, width, height, pixels, pitch, kind))
        if index % 200 == 0:
            print("scanned", index, "bromides", len(found), "missed", len(missed), flush=True)
    print("opened", len(rows) - len(missed), "missed", len(missed), "bromides", len(found))
    print("prefixes", prefixes.most_common(20))
    if missed:
        print("missed sample", missed[:12])
    sizes = collections.Counter((w, h) for *_, w, h, _p, _t, _k in found)
    print("dimensions", sizes.most_common(12))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["folder", "hash", "size", "key", "name", "width", "height", "pixels", "pitch", "kind"])
        writer.writerows(found)


if __name__ == "__main__":
    main()
