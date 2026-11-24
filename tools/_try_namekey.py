# -*- coding: utf-8 -*-
"""Try the filename hash as an AES/RC4 key on a few COMMON files."""
import os
import struct
import zlib

from Crypto.Cipher import AES, ARC4

COMMON = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
MAGICS = (b"GT1G", b"_M1G", b"_N1G", b"_A2G", b"_A1G", b"_L1G", b"OC1G", b"DDS ", b"RIFF", b"\x78\x9c", b"\x78\xda")


def ok(buf):
    if buf[:4] in MAGICS or buf[:3] in (b"\x78\x9c", b"\x78\xda"):
        return True
    try:
        zlib.decompress(buf[:64])
        return True
    except zlib.error:
        return False


def main():
    picked = []
    for name in os.listdir(COMMON):
        path = os.path.join(COMMON, name)
        size = os.path.getsize(path)
        if size < 64 or size > 200_000:
            continue
        head = open(path, "rb").read(4)
        if head[:4] in (b"_L1G", b"NmGr") or head[:4] == b"\x30\x26\xb2\x75":
            continue
        key0 = struct.unpack("<I", head)[0]
        if key0 == 0 or key0 > 0x10000:
            continue
        picked.append(name)
        if len(picked) >= 8:
            break
    for name in picked:
        data = open(os.path.join(COMMON, name), "rb").read(64)
        key = bytes.fromhex(name)
        print("file", name[:16], "size-head", data[:8].hex())
        trials = []
        trials.append(("rc4+0", ARC4.new(key).decrypt(data)))
        trials.append(("rc4+4", data[:4] + ARC4.new(key).decrypt(data[4:])))
        trials.append(("rc4-16", ARC4.new(key[:16]).decrypt(data)))
        for off in (0, 16):
            block = data[off:off + 16]
            if len(block) < 16:
                continue
            trials.append((f"ecb256@{off}", AES.new(key, AES.MODE_ECB).decrypt(block)))
            trials.append((f"cbc256z@{off}", AES.new(key, AES.MODE_CBC, iv=b"\x00" * 16).decrypt(block)))
            trials.append((f"ecb128@{off}", AES.new(key[:16], AES.MODE_ECB).decrypt(block)))
        if len(data) >= 32:
            trials.append(("cbc-iv0", AES.new(key, AES.MODE_CBC, iv=data[:16]).decrypt(data[16:32])))
        for label, out in trials:
            if ok(out):
                print("  HIT", label, out[:16])


if __name__ == "__main__":
    main()
