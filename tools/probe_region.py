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
    ptr = struct.unpack("<Q", (lambda b: b)(
        (ctypes.c_char * 8)()
    ))
    buf = (ctypes.c_char * 8)()
    got = ctypes.c_size_t()
    k32.ReadProcessMemory(handle, ctypes.c_void_p(base + 0x4003838), buf, 8, ctypes.byref(got))
    ptr = struct.unpack("<Q", bytes(buf))[0]
    info = MBI()
    k32.VirtualQueryEx(handle, ctypes.c_void_p(ptr), ctypes.byref(info), ctypes.sizeof(info))
    body = (ctypes.c_char * 16)()
    k32.ReadProcessMemory(handle, ctypes.c_void_p(ptr), body, 16, ctypes.byref(got))
    lines = [
        f"ptr {ptr:#x}",
        f"base {info.BaseAddress:#x} size {info.RegionSize:#x} state {info.State:#x} prot {info.Protect:#x} type {info.Type:#x}",
        f"bytes {bytes(body).hex()} got {got.value}",
    ]
    open(r"D:\Projects\YangHui\DOAXVV\tools\_region.txt", "w").write("\n".join(lines))


if __name__ == "__main__":
    main()
