# -*- coding: utf-8 -*-
"""Find live cipher contexts that point at the runtime seed."""
import ctypes
import struct
from ctypes import wintypes

OUT = r"D:\Projects\YangHui\DOAXVV\tools\_ctx_report.txt"
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
k32.ReadProcessMemory.restype = wintypes.BOOL


class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64),
        ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wintypes.DWORD),
        ("_pad1", wintypes.DWORD),
        ("RegionSize", ctypes.c_uint64),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("_pad2", wintypes.DWORD),
    ]


k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t
lines = []


def log(text):
    lines.append(text)


def read(handle, addr, size):
    buf = (ctypes.c_char * size)()
    got = ctypes.c_size_t()
    ok = k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    if not ok or got.value == 0:
        return None
    return bytes(buf[:got.value])


def main():
    import subprocess
    out = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq DOAX_VV.exe", "/FO", "CSV", "/NH"],
        text=True,
    )
    pid = int(next(row.split(",")[1].strip('"') for row in out.splitlines() if "DOAX_VV" in row))
    handle = k32.OpenProcess(0x0410, False, pid)
    psapi = ctypes.WinDLL("psapi")
    mods = (ctypes.c_void_p * 4)()
    needed = wintypes.DWORD()
    psapi.EnumProcessModules(handle, mods, ctypes.sizeof(mods), ctypes.byref(needed))
    base = mods[0]
    ptr = struct.unpack("<Q", read(handle, base + 0x4003838, 8))[0]
    log(f"pid {pid} base {base:#x} seed {ptr:#x}")
    needle = struct.pack("<Q", ptr)
    addr = 0
    info = MBI()
    found = 0
    while found < 40:
        got = k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(info), ctypes.sizeof(info))
        if not got:
            break
        size = info.RegionSize
        readable = info.State == 0x1000 and info.Protect in (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)
        if readable and 0 < size <= 64 * 1024 * 1024:
            blob = read(handle, info.BaseAddress, size)
            if blob:
                start = 0
                while found < 40:
                    at = blob.find(needle, start)
                    if at < 0:
                        break
                    start = at + 1
                    abs_at = info.BaseAddress + at
                    window = blob[max(0, at - 16):at + 64]
                    rel = at - max(0, at - 16)
                    before = window[:rel]
                    after = window[rel + 8:]
                    log(f"at {abs_at:#x} before {before.hex()} after {after.hex()}")
                    found += 1
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    log(f"found {found}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"error {type(exc).__name__}: {exc}")
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
