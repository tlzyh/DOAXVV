# -*- coding: utf-8 -*-
"""Search the package for a window that decrypts to the captured plaintext."""
import os

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
PLAIN = open(r"D:\Projects\YangHui\DOAXVV\tools\_plain_now.bin", "rb").read(16)
KEYS = [b""] + [bytes.fromhex(item) for item in ("092ff0", "0156553e", "8d452e", "0adb01", "01abfe")]
PKG = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON\4be7efcc93f64e14d7bd7984ef6eeb2ef5ad802ea74cf12ad50a4d39bab71798"


def stream_of(key):
    if not key:
        return SEED
    size = len(SEED) * len(key) // __import__("math").gcd(len(SEED), len(key))
    raw = bytearray(size)
    for index in range(size):
        raw[index] = SEED[index % len(SEED)] ^ key[index % len(key)]
    return bytes(raw)


def ok_byte(cipher, plain, mixed):
    if cipher == 0 or cipher == mixed:
        return plain == cipher
    return plain == (cipher ^ mixed)


def search(blob, plain, stream, label):
    n = len(stream)
    limit = len(blob) - len(plain)
    for offset in range(limit):
        mixed = stream[offset % n]
        if not ok_byte(blob[offset], plain[0], mixed):
            continue
        good = True
        for index in range(1, len(plain)):
            mixed = stream[(offset + index) % n]
            if not ok_byte(blob[offset + index], plain[index], mixed):
                good = False
                break
        if good:
            print("HIT", label, "off", offset)
            return True
    return False


def main():
    blob = open(PKG, "rb").read()
    print("pkg", len(blob), "plain", PLAIN.hex())
    targets = [PLAIN, PLAIN[4:]]
    for key in KEYS:
        stream = stream_of(key)
        for plain in targets:
            found = search(blob, plain, stream, key.hex() or "seed" + ":" + str(len(plain)))
            if found:
                return
        print("done", key.hex() or "seed")
    print("no hit")


if __name__ == "__main__":
    main()
