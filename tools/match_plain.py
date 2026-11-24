# -*- coding: utf-8 -*-
"""Find which hash file decrypts to the captured plaintext prefix."""
import os

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
PLAIN = open(r"D:\Projects\YangHui\DOAXVV\tools\_plain_now.bin", "rb").read()
KEYS = [bytes.fromhex(item) for item in ("092ff0", "0156553e", "8d452e", "0adb01", "01abfe")]
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
NEED = 16


def streams(key):
    size = len(SEED) * len(key) // __import__("math").gcd(len(SEED), len(key))
    raw = bytearray(size)
    for i in range(size):
        raw[i] = SEED[i % len(SEED)] ^ key[i % len(key)]
    return bytes(raw)


def matches(cipher, plain, stream, phase):
    n = len(stream)
    for i in range(NEED):
        value = cipher[i]
        mixed = stream[(phase + i) % n]
        if value == 0 or value == mixed:
            if plain[i] != value:
                return False
        elif plain[i] != (value ^ mixed):
            return False
    return True


def main():
    prepared = [(key, streams(key)) for key in KEYS]
    hits = []
    checked = 0
    for folder in ("COMMON", "HIGH"):
        path = os.path.join(ROOT, folder)
        for name in os.listdir(path):
            full = os.path.join(path, name)
            size = os.path.getsize(full)
            if size < NEED:
                continue
            checked += 1
            with open(full, "rb") as handle:
                cipher = handle.read(NEED)
            for key, stream in prepared:
                # phases that satisfy the first constrained byte
                phases = range(len(stream))
                first_c = cipher[0]
                first_p = PLAIN[0]
                if first_c and first_c != first_p:
                    need = first_c ^ first_p
                    phases = [i for i, mix in enumerate(stream) if mix == need]
                for phase in phases:
                    if matches(cipher, PLAIN, stream, phase):
                        hits.append((folder, name, key.hex(), phase, size))
                        break
    print("plain", PLAIN[:8].hex(), "checked", checked, "hits", len(hits))
    for row in hits[:20]:
        print(row)


if __name__ == "__main__":
    main()
