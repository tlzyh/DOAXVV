# -*- coding: utf-8 -*-
"""List large CPU allocations and search them for shared-pool headers."""
import ctypes
import os
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
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"
OUT = r"D:\Projects\YangHui\DOAXVV\tools\_regions.txt"


def read(handle, addr, size):
    buf = (ctypes.c_char * size)()
    got = ctypes.c_size_t()
    k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    return bytes(buf[:got.value])


def headers():
    chosen = {}
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        size = os.path.getsize(full)
        if size < 1_000_000 or size in chosen:
            continue
        head = open(full, "rb").read(16)
        if head[4:6] == bytes((0x4A, 0x7B)):
            chosen[size] = head
        if len(chosen) >= 6:
            break
    return chosen


def main():
    import subprocess
    text = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq DOAX_VV.exe", "/FO", "CSV", "/NH"], text=True
    )
    pid = int(next(row.split(",")[1].strip('"') for row in text.splitlines() if "DOAX_VV" in row))
    handle = k32.OpenProcess(0x0410, False, pid)
    needles = headers()
    lines = [f"pid {pid}", "needles " + ", ".join(f"{size}:{head[:8].hex()}" for size, head in needles.items())]
    big = []
    found = {size: [] for size in needles}
    addr = 0
    info = MBI()
    while True:
        got = k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(info), ctypes.sizeof(info))
        if not got:
            break
        size = info.RegionSize
        readable = info.State == 0x1000 and info.Protect in (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)
        if readable and size >= 32 * 1024 * 1024:
            big.append((size, info.BaseAddress, info.Protect, info.Type))
        if readable and size:
            offset = 0
            while offset < size:
                step = min(8 * 1024 * 1024, size - offset)
                blob = read(handle, info.BaseAddress + offset, step)
                base = info.BaseAddress + offset
                if blob:
                    for file_size, head in needles.items():
                        if len(found[file_size]) >= 3:
                            continue
                        start = 0
                        while len(found[file_size]) < 3:
                            at = blob.find(head, start)
                            if at < 0:
                                break
                            start = at + 1
                            found[file_size].append(base + at)
                offset += step
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    big.sort(reverse=True)
    lines.append(f"regions>=32MB {len(big)}")
    for size, base, prot, typ in big[:15]:
        lines.append(f"  {base:#x} {size/1024/1024:.1f}MB prot {prot:#x} type {typ:#x}")
    for file_size, addrs in found.items():
        lines.append(f"header {file_size} hits {len(addrs)} " + " ".join(hex(item) for item in addrs))
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
