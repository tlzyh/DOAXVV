# -*- coding: utf-8 -*-
"""Phase-0 (and slice) decrypt of every hash file, then look for real magics.

The earlier zlib sweep only fed 64 bytes to zlib.decompress, so a normal
stream was reported as a miss. This pass decrypts a short prefix and, on a
zlib header, inflates the following bytes.
"""
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
KEYS = [b""] + [
    bytes.fromhex(item)
    for item in (
        "092ff0",
        "076a612e",
        "d655",
        "02ae6d22",
        "01abfe",
        "0156553e",
        "8d452e",
        "0adb01",
    )
]
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
MAGICS = (b"GT1G", b"_M1G", b"_N1G", b"_A1G", b"_A2G", b"TLSK", b"DDS ", b"RIFF")
SLICES = (0, 4, 8, 12, 16, 24, 32, 48, 64)


def stream(key):
    if not key:
        return SEED
    size = len(SEED) * len(key) // __import__("math").gcd(len(SEED), len(key))
    raw = bytearray(size)
    for i in range(size):
        raw[i] = SEED[i % len(SEED)] ^ key[i % len(key)]
    return bytes(raw)


def apply(data, keystream, phase):
    out = bytearray(len(data))
    n = len(keystream)
    for i, value in enumerate(data):
        mixed = keystream[(phase + i) % n]
        if value == 0 or value == mixed:
            out[i] = value
        else:
            out[i] = value ^ mixed
    return bytes(out)


def looks_like(blob):
    found = []
    window = blob[:192]
    for magic in MAGICS:
        at = window.find(magic)
        if at >= 0:
            found.append((magic.decode("ascii"), at, blob[at:at + 12]))
    zpos = window.find(b"\x78\x9c")
    if zpos < 0:
        zpos = window.find(b"\x78\xda")
    return found, zpos


def try_inflate(folder, name, key_name, phase, origin, plain):
    zpos = plain.find(b"\x78\x9c")
    if zpos < 0:
        zpos = plain.find(b"\x78\xda")
    if zpos < 0 or zpos > 64:
        return None
    for candidate in (plain[zpos:], plain[zpos:zpos + 65536]):
        try:
            inflated = zlib.decompress(candidate)
        except zlib.error:
            continue
        if len(inflated) >= 16:
            return zpos, len(inflated), inflated[:16]
    return None


def main():
    prepared = [(key.hex() or "seed", stream(key)) for key in KEYS]
    hits = []
    prefixes = {}
    checked = 0
    folders = []
    for rel in ("COMMON", "HIGH", os.path.join("DL", "COMMON"), os.path.join("DL", "HIGH")):
        folder_path = os.path.join(ROOT, rel)
        if os.path.isdir(folder_path):
            folders.append((rel, folder_path))
    for rel, folder_path in folders:
        for name in os.listdir(folder_path):
            full = os.path.join(folder_path, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size < 32:
                continue
            checked += 1
            with open(full, "rb") as handle:
                head = handle.read(256)
            prefixes[head[:4]] = prefixes.get(head[:4], 0) + 1
            for key_name, keystream in prepared:
                plain = apply(head, keystream, 0)
                found, _zpos = looks_like(plain)
                inflated = try_inflate(rel, name, key_name, 0, 0, plain)
                if found or inflated:
                    hits.append((rel, name[:16], size, key_name, "phase0", found, inflated))
                if len(hits) >= 12:
                    break
                for origin in SLICES[1:]:
                    if origin + 8 > len(head):
                        break
                    for phase in (0, origin):
                        piece = apply(head[origin:origin + 8], keystream, phase)
                        if piece[:4] not in MAGICS and piece[:2] not in (b"\x78\x9c", b"\x78\xda"):
                            continue
                        wide = apply(head[origin:origin + 192], keystream, phase)
                        found, _zpos = looks_like(wide)
                        inflated = try_inflate(rel, name, key_name, phase, origin, wide)
                        if found or inflated:
                            hits.append(
                                (rel, name[:16], size, key_name, f"off{origin}:ph{phase}", found, inflated)
                            )
                    if len(hits) >= 12:
                        break
                if len(hits) >= 12:
                    break
            if len(hits) >= 12:
                break
        if len(hits) >= 12:
            break
    print("checked", checked, "hits", len(hits))
    top = sorted(prefixes.items(), key=lambda item: item[1], reverse=True)[:12]
    print("top prefixes", [(blob.hex(), count) for blob, count in top])
    for row in hits:
        print(row)


if __name__ == "__main__":
    main()
