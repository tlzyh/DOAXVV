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


def read(handle, addr, size):
    buf = (ctypes.c_char * size)()
    got = ctypes.c_size_t()
    ok = k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    if not ok or not got.value:
        return b""
    return bytes(buf[:got.value])


def strings(blob):
    out = []
    cur = bytearray()
    for b in blob:
        if 32 <= b < 127:
            cur.append(b)
        else:
            if len(cur) >= 6:
                out.append(cur.decode())
            cur = bytearray()
    if len(cur) >= 6:
        out.append(cur.decode())
    return out


def main():
    import subprocess
    out = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq DOAX_VV.exe", "/FO", "CSV", "/NH"], text=True
    )
    pid = int(next(row.split(",")[1].strip('"') for row in out.splitlines() if "DOAX_VV" in row))
    handle = k32.OpenProcess(0x0410, False, pid)
    lines = []
    for ctx in (0xFEFE2330, 0xFF0006D0, 0xFF01E650):
        base = ctx - 0x1DD90
        head = read(handle, base, 0x180)
        lines.append(f"obj {base:#x} head {head[:64].hex()}")
        lines.append("strings " + " | ".join(strings(head)[:12]))
        # also a window around the context for a path
        around = read(handle, ctx - 0x200, 0x280)
        lines.append("near " + " | ".join(strings(around)[:12]))
    open(r"D:\Projects\YangHui\DOAXVV\tools\_obj.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
