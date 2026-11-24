# -*- coding: utf-8 -*-
import struct

blob = open(r"D:\Projects\YangHui\DOAXVV\tools\_mis_za.bin", "rb").read()


def stats(at, count, kind):
    if kind == "u16":
        vals = struct.unpack_from("<" + "H" * count, blob, at)
    else:
        vals = struct.unpack_from("<" + "I" * count, blob, at)
    print(kind, hex(at), "min", min(vals), "max", max(vals), "uniq", len(set(vals)))
    print(" ", vals[:16])


def main():
    for at in (0xD650, 0xD660, 0x42CD0, 0x1AC60):
        if at + 64 > len(blob):
            continue
        print("\nregion", hex(at), blob[at:at + 32].hex())
        stats(at, 24, "u16")
        stats(at, 12, "u32")


if __name__ == "__main__":
    main()
