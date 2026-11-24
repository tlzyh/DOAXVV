# -*- coding: utf-8 -*-
"""Look for an offset table inside a shared HIGH blob."""
import os
import struct

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"


def load(size):
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        if os.path.getsize(full) == size:
            return os.path.basename(name)[:16], open(full, "rb").read()
    raise SystemExit(size)


def longest_increasing(data, limit):
    best = (0, 0)
    run = 0
    start = 0
    prev = -1
    step = 4
    for index in range(0, len(data) - 4, step):
        value = struct.unpack_from("<I", data, index)[0]
        if 0 < value < limit and value > prev:
            if run == 0:
                start = index
            run += 1
            prev = value
        else:
            if run > best[0]:
                best = (run, start)
            run = 0
            prev = -1
    if run > best[0]:
        best = (run, start)
    return best


def main():
    for size in (17312, 2460000):
        name, data = load(size)
        run, at = longest_increasing(data, size)
        print(name, size, "best run", run, "at", hex(at))
        if run:
            vals = [struct.unpack_from("<I", data, at + i * 4)[0] for i in range(min(run, 8))]
            print("  ", vals)


if __name__ == "__main__":
    main()
