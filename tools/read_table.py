# -*- coding: utf-8 -*-
"""Dump the live archive table and look for decoded resource headers."""
import ctypes
import struct
from ctypes import wintypes

OUT = r"D:\Projects\YangHui\DOAXVV\tools\_table.txt"
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
    lines = [f"pid {pid} base {base:#x}"]
    table = read(handle, base + 0x4011BE8 - 8, 0x40 * 8 + 8)
    if table:
        for i in range(8):
            rec = table[i * 0x40:(i + 1) * 0x40]
            q = struct.unpack_from("<4Q", rec, 0)
            d = struct.unpack_from("<4I", rec, 0x20)
            lines.append(f"rec {i} q={[hex(x) for x in q]} d={[hex(x) for x in d]} raw {rec.hex()}")
    needles = (b"GT1G0", b"_N1G0", b"_A2G0", b"_A1G0", b"GT1G", b"_N1G0000")
    addr = 0
    info = MBI()
    hits = []
    while len(hits) < 20:
        got = k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(info), ctypes.sizeof(info))
        if not got:
            break
        size = info.RegionSize
        readable = info.State == 0x1000 and info.Protect in (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)
        in_image = base <= info.BaseAddress < base + 0x8000000
        if readable and 0 < size <= 64 * 1024 * 1024 and not in_image:
            blob = read(handle, info.BaseAddress, size)
            if blob:
                for magic in needles:
                    start = 0
                    while len(hits) < 20:
                        at = blob.find(magic, start)
                        if at < 0:
                            break
                        start = at + 1
                        sample = blob[at:at + 16]
                        hits.append((info.BaseAddress + at, sample))
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    lines.append(f"hits {len(hits)}")
    for at, sample in hits:
        lines.append(f"{at:#x} {sample}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_table.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
