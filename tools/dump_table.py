# -*- coding: utf-8 -*-
import struct

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000
VA = 0x1433C9B00


def file_off(data, va):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    off = pe + 24 + opt
    rva = va - IMAGE
    for i in range(nsec):
        base = off + i * 40
        vsz, sva, rsz, raw = struct.unpack_from("<IIII", data, base + 8)
        if sva <= rva < sva + max(vsz, rsz):
            return raw + (rva - sva)
    raise SystemExit(hex(va))


def main():
    data = open(EXE, "rb").read()
    off = file_off(data, VA)
    blob = data[off:off + 0x400]
    for i in range(0, len(blob), 16):
        print(f"{VA+i:x} {blob[i:i+16].hex()}")


if __name__ == "__main__":
    main()
