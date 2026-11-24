# -*- coding: utf-8 -*-
import ctypes
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
k32.ReadProcessMemory.restype = wintypes.BOOL
ADDRS = (0x11B4534A0, 0xFDFC43A0, 0xFEFE2360, 0x11A4534C8, 0xFDF44380)


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
    lines = []
    for addr in ADDRS:
        blob = read(handle, addr, 48)
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in blob)
        lines.append(f"{addr:#x} {blob.hex()} {text}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_peek.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
