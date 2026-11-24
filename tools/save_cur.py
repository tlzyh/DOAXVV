# -*- coding: utf-8 -*-
import ctypes
import struct
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
k32.ReadProcessMemory.restype = wintypes.BOOL


def read(handle, addr, size):
    buf = (ctypes.c_char * size)()
    got = ctypes.c_size_t()
    k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    return bytes(buf[:got.value])


def main():
    import subprocess
    out = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq DOAX_VV.exe", "/FO", "CSV", "/NH"], text=True
    )
    pid = int(next(row.split(",")[1].strip('"') for row in out.splitlines() if "DOAX_VV" in row))
    handle = k32.OpenProcess(0x0410, False, pid)
    head = read(handle, 0xFDF44380, 8)
    size = struct.unpack_from("<I", head, 0)[0]
    take = min(size + 8, 1024 * 1024) if 16 < size < 4 * 1024 * 1024 else 65536
    blob = read(handle, 0xFDF44380, take)
    open(r"D:\Projects\YangHui\DOAXVV\tools\_plain_now.bin", "wb").write(blob)
    open(r"D:\Projects\YangHui\DOAXVV\tools\_plain_now.txt", "w").write(
        f"head {head.hex()} size {size:#x} got {len(blob)}\n"
    )


if __name__ == "__main__":
    main()
