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
    blob = read(handle, base + 0x4010DE0, 0x4800)
    lines = [f"base {base:#x} got {len(blob) if blob else 0}"]
    if not blob:
        open(r"D:\Projects\YangHui\DOAXVV\tools\_catalog.txt", "w").write("none")
        return
    shown = 0
    for i in range(0, len(blob), 0x18):
        rec = blob[i:i + 0x18]
        if rec == b"\x00" * 0x18:
            continue
        ident, a, b = struct.unpack("<IxxxxQQ", rec)
        text = ""
        if b and b < 0x7fffffffffff:
            sample = read(handle, b, 64)
            if sample:
                text = "".join(chr(c) if 32 <= c < 127 else "." for c in sample)
        lines.append(f"{i//0x18:4d} id {ident:#x} a {a:#x} b {b:#x} {text[:48]}")
        shown += 1
        if shown > 40:
            break
    lines.append(f"shown {shown}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_catalog.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
