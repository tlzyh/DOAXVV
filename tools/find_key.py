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
NEEDLE = b"WUeq032FJnLBUBmW"


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
    addr = 0
    info = MBI()
    lines = []
    while len(lines) < 12:
        got = k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(info), ctypes.sizeof(info))
        if not got:
            break
        size = info.RegionSize
        readable = info.State == 0x1000 and info.Protect in (0x04, 0x02, 0x08, 0x40, 0x20, 0x80)
        if readable and 0 < size <= 64 * 1024 * 1024:
            blob = read(handle, info.BaseAddress, size)
            start = 0
            while len(lines) < 12:
                at = blob.find(NEEDLE, start)
                if at < 0:
                    break
                start = at + 1
                sample = blob[max(0, at - 48):at + 64]
                text = "".join(chr(c) if 32 <= c < 127 else "." for c in sample)
                lines.append(f"{info.BaseAddress + at:#x} {text}")
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    open(r"D:\Projects\YangHui\DOAXVV\tools\_keyhits.txt", "w", encoding="utf-8").write("\n".join(lines) or "none")


if __name__ == "__main__":
    main()
