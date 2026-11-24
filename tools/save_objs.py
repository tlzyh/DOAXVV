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
SIZE = 0x1DE10
BASES = (0xFEFC45A0, 0xFEFE2940, 0xFF0008C0)


def read(handle, addr, size):
    buf = (ctypes.c_char * size)()
    got = ctypes.c_size_t()
    ok = k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    return bytes(buf[:got.value])


def main():
    import subprocess
    out = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq DOAX_VV.exe", "/FO", "CSV", "/NH"], text=True
    )
    pid = int(next(row.split(",")[1].strip('"') for row in out.splitlines() if "DOAX_VV" in row))
    handle = k32.OpenProcess(0x0410, False, pid)
    lines = []
    for addr in BASES:
        blob = read(handle, addr, SIZE)
        path = rf"D:\Projects\YangHui\DOAXVV\tools\_obj_{addr:x}.bin"
        open(path, "wb").write(blob)
        lines.append(f"{addr:#x} {len(blob)}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_objs.txt", "w").write("\n".join(lines))


if __name__ == "__main__":
    main()
