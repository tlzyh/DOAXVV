# -*- coding: utf-8 -*-
"""Decrypt a DOAXVV hash file with the live skip-zero cipher.

The running game builds a 344-byte seed. Each archive then mixes in a short
key, the nonzero big-endian bytes of (index * 0x77) // 11. Bytes that are 0
or equal to the key byte are left unchanged. The plaintext is a little-endian
size followed by a zlib stream, padded to 16 bytes, then the next chunk.
"""
import argparse
import os
import sys
import zlib

SEED_PATH = os.path.join(os.path.dirname(__file__), "_seed_live.bin")
SEED = open(SEED_PATH, "rb").read()


def key_from_index(index):
    dword = ((index * 0x77) // 11) & 0xFFFFFFFF
    return bytes(b for b in dword.to_bytes(4, "big") if b)


def decrypt(data, key, seed=SEED):
    if isinstance(key, str):
        key = bytes.fromhex(key)
    out = bytearray(len(data))
    seed_len = len(seed)
    key_len = len(key)
    for index, value in enumerate(data):
        mixed = seed[index % seed_len]
        if key_len:
            mixed ^= key[index % key_len]
        if value == 0 or value == mixed:
            out[index] = value
        else:
            out[index] = value ^ mixed
    return bytes(out)


def iter_pages(plain):
    pos = 0
    while pos + 6 <= len(plain):
        if plain[pos + 4:pos + 6] not in (b"\x78\x9c", b"\x78\xda", b"\x78\x01"):
            nxt = (pos + 16) & ~15
            if nxt <= pos or nxt + 6 > len(plain):
                break
            if plain[nxt + 4:nxt + 6] not in (b"\x78\x9c", b"\x78\xda", b"\x78\x01"):
                break
            pos = nxt
            continue
        obj = zlib.decompressobj()
        try:
            inflated = obj.decompress(plain[pos + 4:]) + obj.flush()
        except zlib.error:
            break
        used = len(plain) - pos - 4 - len(obj.unused_data)
        yield pos, inflated
        pos = (pos + 4 + used + 15) & ~15


def first_page(data, key):
    plain = decrypt(data, key)
    for _pos, inflated in iter_pages(plain):
        return inflated
    return None


def magic_of(blob):
    if not blob:
        return ""
    if blob.startswith(b"TLSK"):
        return "TLSK" + blob[4:8].decode("ascii", "replace")
    if blob.startswith(b"TMC"):
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
    if b"DDS " in blob[:512]:
        return "DDS"
    text = blob[:8]
    if all(32 <= b < 127 for b in text[:4]):
        return text.split(b"\x00", 1)[0].decode("ascii", "replace")
    return blob[:4].hex()


def main():
    parser = argparse.ArgumentParser(description="Decrypt one DOAXVV hash file")
    parser.add_argument("path")
    parser.add_argument("key", help="hex key, or an integer cipher index")
    parser.add_argument("out", nargs="?")
    args = parser.parse_args()
    key = key_from_index(int(args.key)) if args.key.isdigit() else bytes.fromhex(args.key)
    data = open(args.path, "rb").read()
    pages = list(iter_pages(decrypt(data, key)))
    if not pages:
        print("no zlib page", file=sys.stderr)
        return 1
    print("pages", len(pages), "magic", magic_of(pages[0][1]), "first", len(pages[0][1]))
    if args.out:
        blob = b"".join(page for _pos, page in pages)
        open(args.out, "wb").write(blob)
        print("wrote", args.out, len(blob))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
