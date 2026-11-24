# -*- coding: utf-8 -*-
"""See whether same-type files share a stream-cipher keystream."""
import os
import struct

COMMON = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"


def load_two(prefix_a, prefix_b=None, key=None):
    found = []
    for name in os.listdir(COMMON):
        path = os.path.join(COMMON, name)
        with open(path, "rb") as handle:
            head = handle.read(4)
        if key is not None and struct.unpack("<I", head)[0] != key:
            continue
        if prefix_a and not name.startswith(prefix_a) and (prefix_b is None or not name.startswith(prefix_b)):
            if key is None:
                continue
        size = os.path.getsize(path)
        if size < 64:
            continue
        found.append(path)
        if len(found) >= 2:
            break
    blobs = [open(path, "rb").read() for path in found]
    return found, blobs


def report(label, a, b):
    n = min(len(a), len(b), 64)
    x = bytes(a[i] ^ b[i] for i in range(n))
    zeros = x.count(0)
    print(label, "xor zeros in", n, "=", zeros)
    print(" ", x[:32].hex())


def main():
    # same type 0xc61c, two 2544-byte files from earlier prefixes
    paths = []
    blobs = []
    for name in os.listdir(COMMON):
        path = os.path.join(COMMON, name)
        size = os.path.getsize(path)
        if size != 2544:
            continue
        with open(path, "rb") as handle:
            head = handle.read(4)
        if struct.unpack("<I", head)[0] != 0xC61C:
            continue
        blobs.append(open(path, "rb").read())
        paths.append(name[:12])
        if len(blobs) == 3:
            break
    print("same type", paths)
    report("same 0-1", blobs[0], blobs[1])
    report("same 0-2", blobs[0], blobs[2])
    # a different type, similar size
    other = None
    for name in os.listdir(COMMON):
        path = os.path.join(COMMON, name)
        if os.path.getsize(path) != 2624:
            continue
        data = open(path, "rb").read()
        if struct.unpack_from("<I", data, 0)[0] != 0xC61C:
            other = data
            print("other", name[:12], hex(struct.unpack_from("<I", data, 0)[0]))
            break
    if other:
        report("diff type", blobs[0], other)
    # zero rate in a large file
    for name in os.listdir(COMMON):
        path = os.path.join(COMMON, name)
        if os.path.getsize(path) < 500000 or os.path.getsize(path) > 800000:
            continue
        data = open(path, "rb").read(65536)
        if data[:4] == b"_L1G" or data[:4] == bytes.fromhex("3026b275"):
            continue
        rate = data[4:].count(0) / (len(data) - 4)
        print("zero rate", name[:12], round(rate, 4), "head", data[:8].hex())
        break


if __name__ == "__main__":
    main()
