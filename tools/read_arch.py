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
        return b""
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
    blob = read(handle, base + 0x4003008 - 8, 0x40 * 0x100 + 8)
    lines = [f"base {base:#x} got {len(blob)}"]
    shown = 0
    for i in range(0x100):
        rec = blob[8 + i * 0x40:8 + (i + 1) * 0x40]
        if len(rec) < 0x40 or rec == b"\x00" * 0x40:
            continue
        index = struct.unpack_from("<Q", rec, 0)[0]
        state = struct.unpack_from("<I", rec, 0x18)[0]
        ident = struct.unpack_from("<I", rec, 0x10)[0]
        before = struct.unpack_from("<Q", blob, i * 0x40)[0]
        lines.append(f"{i} state {state:#x} index {index:#x} id {ident:#x} prev {before:#x} head {rec[:16].hex()}")
        shown += 1
        if shown > 30:
            break
    lines.append(f"shown {shown}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_arch.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
