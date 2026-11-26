# -*- coding: utf-8 -*-
"""Decrypt a DOAXVV hash file with the live skip-zero cipher.

The running game builds a 344-byte seed. Each archive then mixes in a short
key, the nonzero big-endian bytes of (index * 0x77) // 11, where index is the
total inflated size of the file. Bytes that are 0 or equal to the mixed byte
are left unchanged. The plaintext is a little-endian u32 followed by a zlib
stream, padded to 16 bytes, then the next page.
"""
import argparse
import os
import re
import sys
import zlib

import numpy as np

SEED_PATH = os.path.join(os.path.dirname(__file__), "_seed_live.bin")
SEED = open(SEED_PATH, "rb").read()
_SEED = np.frombuffer(SEED, dtype=np.uint8)
ZLIB_SECOND = (0x01, 0x5E, 0x9C, 0xDA)


def key_from_index(index):
    dword = ((index * 0x77) // 11) & 0xFFFFFFFF
    return bytes(b for b in dword.to_bytes(4, "big") if b)


def sizes_for_key(key):
    """Inflated sizes whose derived key is exactly `key`."""
    if isinstance(key, str):
        key = bytes.fromhex(key)
    found = set()
    n = len(key)
    if not 1 <= n <= 4:
        return []
    for mask in range(16):
        if bin(mask).count("1") != n:
            continue
        parts = iter(key)
        dword = 0
        for bit in range(4):
            dword = (dword << 8) | (next(parts) if mask & (8 >> bit) else 0)
        base = (dword * 11) // 0x77
        for size in range(max(base - 1, 0), base + 3):
            if key_from_index(size) == key:
                found.add(size)
    return sorted(found)


def _mixed(length, key, origin=0):
    pos = np.arange(origin, origin + length, dtype=np.int64)
    mixed = _SEED[pos % len(_SEED)]
    if key:
        mixed = mixed ^ np.frombuffer(key, dtype=np.uint8)[pos % len(key)]
    return mixed


def decrypt(data, key, seed=None):
    if isinstance(key, str):
        key = bytes.fromhex(key)
    if seed is not None and seed != SEED:
        raise ValueError("only the live seed is supported")
    cipher = np.frombuffer(data, dtype=np.uint8)
    mixed = _mixed(len(cipher), key)
    plain = np.where((cipher == 0) | (cipher == mixed), cipher, cipher ^ mixed)
    return plain.tobytes()


def iter_pages(plain):
    pos = 0
    while pos + 6 <= len(plain):
        if plain[pos + 4] != 0x78 or plain[pos + 5] not in ZLIB_SECOND:
            nxt = (pos + 16) & ~15
            if nxt <= pos or nxt + 6 > len(plain):
                break
            if plain[nxt + 4] != 0x78 or plain[nxt + 5] not in ZLIB_SECOND:
                break
            pos = nxt
            continue
        obj = zlib.decompressobj()
        try:
            inflated = obj.decompress(plain[pos + 4:]) + obj.flush()
        except zlib.error:
            break
        if not obj.eof:
            break
        used = len(plain) - pos - 4 - len(obj.unused_data)
        yield pos, inflated
        pos = (pos + 4 + used + 15) & ~15


def first_page(data, key):
    plain = decrypt(data, key)
    for _pos, inflated in iter_pages(plain):
        return inflated
    return None


def inflate_all(data, key):
    return b"".join(page for _pos, page in iter_pages(decrypt(data, key)))


def _mixed_options(cipher, plain):
    """Mixed bytes that turn `plain` into `cipher`."""
    if cipher == 0:
        return []
    if cipher == plain:
        return [0, cipher]
    return [cipher ^ plain]


def _four_byte_keys(k4, k5):
    top = (k4 << 24) | (k5 << 16)
    sizes = np.arange((top * 11) // 0x77, ((top + 0x10000) * 11) // 0x77 + 2, dtype=np.int64)
    dword = (sizes * 0x77) // 11
    parts = np.stack([(dword >> shift) & 0xFF for shift in (24, 16, 8, 0)], axis=1)
    keep = (parts[:, 0] == k4) & (parts[:, 1] == k5) & (parts[:, 2] != 0) & (parts[:, 3] != 0)
    return np.unique(parts[keep].astype(np.uint8), axis=0)


def candidate_keys(head):
    """Short keys consistent with a zlib header at offset 4, as arrays grouped by length."""
    groups = []
    for second in ZLIB_SECOND:
        for m4 in _mixed_options(head[4], 0x78):
            for m5 in _mixed_options(head[5], second):
                k4 = SEED[4] ^ m4
                k5 = SEED[5] ^ m5
                if not (k4 and k5):
                    continue
                if k4 == k5:
                    groups.append(np.array([[k4]], dtype=np.uint8))
                groups.append(np.array([[k4, k5]], dtype=np.uint8))
                three = np.empty((255, 3), dtype=np.uint8)
                three[:, 0] = np.arange(1, 256)
                three[:, 1] = k4
                three[:, 2] = k5
                groups.append(three)
                groups.append(_four_byte_keys(k4, k5))
    return [group for group in groups if len(group)]


def _batch_heads(head, keys):
    """Decrypt `head` under every row of `keys` (same key length)."""
    length = len(head)
    cols = np.arange(length)
    cipher = np.frombuffer(head, dtype=np.uint8)
    stream = keys[:, cols % keys.shape[1]] ^ _SEED[cols % len(_SEED)]
    return np.where((cipher == 0) | (cipher == stream), cipher, cipher ^ stream)


def _inflates(plain):
    obj = zlib.decompressobj()
    try:
        obj.decompress(plain)
    except zlib.error:
        return False
    return True


def recover_key(data, hint=(), reader=None):
    """Return the short key that inflates the first page, or None.

    When several keys inflate the first page, `reader()` must return the whole
    file; the key whose derived size matches the inflated size wins.
    """
    head = bytes(data[:96])
    if len(head) < 8:
        return None
    sample = data[:65536]
    for key in hint:
        if first_page(sample, key) is not None:
            return key
    passing = []
    for keys in candidate_keys(head):
        plains = _batch_heads(head, keys)
        for row, plain in zip(keys, plains):
            if not _inflates(plain[4:].tobytes()):
                continue
            key = row.tobytes()
            if key not in passing and first_page(sample, key) is not None:
                passing.append(key)
    if len(passing) <= 1 or reader is None:
        return passing[0] if passing else None
    full = reader()
    for key in passing:
        if key_from_index(len(inflate_all(full, key))) == key:
            return key
    return passing[0]


def magic_of(blob, plain_size=None):
    if not blob:
        return ""
    if blob.startswith(b"TLSK"):
        return "TLSK" + blob[4:8].decode("ascii", "replace")
    if blob.startswith(b"TMC\x00"):
        return "TMC"
    if blob.startswith(b"SCENE"):
        return "SCENE"
    if blob.startswith(b"CONTE"):
        return "CONTE"
    if blob.startswith(b"clip"):
        return "clip"
    if blob.startswith(b"LCSK"):
        return blob[:8].decode("ascii", "replace")
    if blob.startswith(b"char_dat"):
        return "char_dat"
    if blob.startswith(b"ColorLis"):
        return "ColorLis"
    if blob.startswith(b"tdpack"):
        return "tdpack"
    if blob.startswith(b"contact_"):
        return "contact"
    if blob.startswith(b"_S2G"):
        return blob[:8].decode("ascii", "replace")
    if len(blob) >= 8:
        count, total = int.from_bytes(blob[:4], "little"), int.from_bytes(blob[4:8], "little")
        if 1 <= count <= 8 and plain_size and total == plain_size:
            return "TMCL"
    if b"DDS " in blob[:512]:
        return "DDS"
    text = re.match(rb"[A-Za-z0-9_.]*", blob[:8]).group()
    if len(text) >= 4:
        return text.decode("ascii")
    return blob[:4].hex()


def main():
    parser = argparse.ArgumentParser(description="Decrypt one DOAXVV hash file")
    parser.add_argument("path")
    parser.add_argument("key", nargs="?", help="hex key, integer inflated size, or omit to recover")
    parser.add_argument("out", nargs="?")
    args = parser.parse_args()
    data = open(args.path, "rb").read()
    if args.key is None or args.key == "auto":
        key = recover_key(data)
        if key is None:
            print("no key found", file=sys.stderr)
            return 1
    elif args.key.isdigit():
        key = key_from_index(int(args.key))
    else:
        key = bytes.fromhex(args.key)
    pages = list(iter_pages(decrypt(data, key)))
    if not pages:
        print("no zlib page", file=sys.stderr)
        return 1
    total = sum(len(page) for _pos, page in pages)
    print("key", key.hex(), "pages", len(pages), "plain", total,
          "magic", magic_of(pages[0][1], total), "size_ok", key_from_index(total) == key)
    if args.out:
        blob = b"".join(page for _pos, page in pages)
        open(args.out, "wb").write(blob)
        print("wrote", args.out, len(blob))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
