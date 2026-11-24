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
    ok = k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    if not ok or not got.value:
        return None
    return bytes(buf[:got.value])


def main():
    import subprocess
    out = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq DOAX_VV.exe", "/FO", "CSV", "/NH"], text=True
    )
    pid = int(next(row.split(",")[1].strip('"') for row in out.splitlines() if "DOAX_VV" in row))
    handle = k32.OpenProcess(0x0410, False, pid)
    psapi = ctypes.WinDLL("psapi")
    mods = (ctypes.c_void_p * 4)()
    needed = wintypes.DWORD()
    psapi.EnumProcessModules(handle, mods, ctypes.sizeof(mods), ctypes.byref(needed))
    base = mods[0]
    lines = [f"base {base:#x}"]
    ptr = struct.unpack("<Q", read(handle, base + 0x6BF5F40, 8))[0]
    lines.append(f"fs {ptr:#x}")
    if ptr:
        obj = read(handle, ptr, 0x140)
        lines.append(obj.hex())
        inner = struct.unpack_from("<Q", obj, 0x108)[0]
        lines.append(f"inner {inner:#x}")
        if inner:
            body = read(handle, inner, 0x80)
            lines.append(body.hex() if body else "no")
    # also the qword just before, in case the RVA is off by the instruction
    for delta in (-8, 0, 8, 0x10):
        raw = read(handle, base + 0x6BF5F40 + delta, 8)
        lines.append(f"delta {delta} {raw.hex() if raw else None}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_fs.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
