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


def main():
    import subprocess
    out = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq DOAX_VV.exe", "/FO", "CSV", "/NH"], text=True
    )
    pid = int(next(row.split(",")[1].strip('"') for row in out.splitlines() if "DOAX_VV" in row))
    handle = k32.OpenProcess(0x0410, False, pid)
    addr = 0x109BE2DA0 - 0x800
    buf = (ctypes.c_char * 0x2000)()
    got = ctypes.c_size_t()
    k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, 0x2000, ctypes.byref(got))
    data = bytes(buf[:got.value])
    open(r"D:\Projects\YangHui\DOAXVV\tools\_strings.bin", "wb").write(data)
    text = "".join(chr(c) if 32 <= c < 127 else "\n" for c in data)
    parts = [part for part in text.split("\n") if len(part) >= 4]
    open(r"D:\Projects\YangHui\DOAXVV\tools\_strings.txt", "w", encoding="utf-8").write("\n".join(parts))


if __name__ == "__main__":
    main()
