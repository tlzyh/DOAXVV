# -*- coding: utf-8 -*-
import bz2
import lzma
import os
import zlib

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"


def load(folder, size=None, pair=None):
    path = os.path.join(ROOT, folder)
    for name in os.listdir(path):
        full = os.path.join(path, name)
        file_size = os.path.getsize(full)
        if size is not None and file_size != size:
            continue
        head = open(full, "rb").read(8)
        if pair is not None and head[4:6] != pair:
            continue
        return open(full, "rb").read()
    raise SystemExit("missing")


def attempt(label, data):
    print("==", label, len(data), data[:8].hex())
    for off in (0, 4, 8, 12, 16, 32):
        chunk = data[off:]
        for name, func in (
            ("lzma", lzma.decompress),
            ("bz2", bz2.decompress),
        ):
            try:
                out = func(chunk)
                print(" ", name, off, len(out), out[:8])
                return
            except Exception:
                pass
        for wbits in (15, -15, 31):
            try:
                out = zlib.decompress(chunk, wbits)
                if len(out) > 32:
                    print(" ", "zlib", wbits, off, len(out), out[:8])
                    return
            except Exception:
                pass
    print("  none")


def main():
    attempt("pool", load("HIGH", size=17312))
    attempt("f29c", load("COMMON", pair=bytes.fromhex("f29c")))
    attempt("big", load("HIGH", size=2460000)[:200000])


if __name__ == "__main__":
    main()
