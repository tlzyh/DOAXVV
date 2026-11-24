# -*- coding: utf-8 -*-
"""Try the embedded 32-byte key against one resource file."""
import hashlib
import os
import struct
import zlib

from Crypto.Cipher import AES, ARC4

COMMON = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
KEY = b"Qqp7eSOMDzvb9YpIgXUYZdIo9RAu7EKb"
OLD = bytes.fromhex("4686048e796cd48ad484ec7f6d22a8ea")
MAGICS = (b"GT1G", b"_M1G", b"_N1G", b"_A2G", b"_A1G", b"_L1G", b"OC1G", b"DDS ", b"RIFF", b"\x78\x9c", b"\x78\xda")


def sample():
    for name in os.listdir(COMMON):
        path = os.path.join(COMMON, name)
        size = os.path.getsize(path)
        if 20000 < size < 40000:
            data = open(path, "rb").read()
            if struct.unpack_from("<I", data, 0)[0] > 0xFFFF:
                continue
            if data[:4] in (b"_L1G",):
                continue
            return name, data
    raise RuntimeError("no sample")


def consider(label, blob):
    head = blob[:16]
    for magic in MAGICS:
        if blob.startswith(magic) or blob[4:4 + len(magic)] == magic:
            print(" HIT", label, magic, head.hex())
            return True
    if blob[:2] in (b"\x78\x9c", b"\x78\xda", b"\x78\x01"):
        try:
            out = zlib.decompress(blob)
        except zlib.error:
            return False
        print(" ZLIB", label, len(out), out[:16])
        return True
    return False


def main():
    name, data = sample()
    print("sample", name[:16], len(data), data[:16].hex())
    seeds = {
        "ascii32": KEY,
        "ascii16": KEY[:16],
        "old16": OLD,
        "sha256": hashlib.sha256(KEY).digest(),
        "md5": hashlib.md5(KEY).digest(),
    }
    offsets = (0, 4, 8, 16)
    for seed_name, key in seeds.items():
        for off in offsets:
            body = data[off:]
            if len(key) in (16, 24, 32):
                n = len(body) - (len(body) % 16)
                chunk = body[:n]
                if n >= 16:
                    for mode_name, cipher in (
                        ("ecb", AES.new(key, AES.MODE_ECB)),
                        ("cbc0", AES.new(key, AES.MODE_CBC, iv=b"\x00" * 16)),
                    ):
                        plain = cipher.decrypt(chunk[:256])
                        consider(f"aes-{len(key)}-{mode_name} off{off} {seed_name}", plain)
                    if off == 0 and len(data) >= 32:
                        iv, rest = data[:16], data[16:]
                        n2 = len(rest) - (len(rest) % 16)
                        plain = AES.new(key, AES.MODE_CBC, iv=iv).decrypt(rest[:n2][:256])
                        consider(f"aes-{len(key)}-cbciv off0 {seed_name}", plain)
            # rc4
            plain = ARC4.new(key).decrypt(body[:256])
            consider(f"rc4 off{off} {seed_name}", plain)
    # per-file: rc4 key = first dword + master
    seed = struct.pack("<I", struct.unpack_from("<I", data, 0)[0])
    for key in (seed + KEY, KEY + seed, seed):
        plain = ARC4.new(key).decrypt(data[4:260])
        consider(f"rc4-seed {key[:8].hex()}", plain)
    print("done")


if __name__ == "__main__":
    main()
