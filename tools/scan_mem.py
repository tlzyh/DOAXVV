# -*- coding: utf-8 -*-
"""See which resource kinds are currently decoded in the running game."""
import ctypes
from ctypes import wintypes

OUT = r"D:\Projects\YangHui\DOAXVV\tools\_scan.txt"
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
NEEDLES = (b"GT1G0", b"_N1G0", b"_A2G0", b"_A1G0", b"DDS ", b"OggS", b"KOVS", b"window_00", b"PNG", b"RIFF")


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
    counts = {n: 0 for n in NEEDLES}
    samples = []
    addr = 0
    info = MBI()
    private = 0
    while True:
        got = k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(info), ctypes.sizeof(info))
        if not got:
            break
        size = info.RegionSize
        readable = info.State == 0x1000 and info.Protect in (0x04, 0x02, 0x08, 0x40, 0x20, 0x80)
        in_image = base <= info.BaseAddress < base + 0x8000000
        if readable and not in_image and 0 < size <= 256 * 1024 * 1024:
            private += size
            blob = read(handle, info.BaseAddress, min(size, 32 * 1024 * 1024))
            for needle in NEEDLES:
                counts[needle] += blob.count(needle)
            if size >= 1024 * 1024 and len(samples) < 12:
                samples.append((info.BaseAddress, size, blob[:32].hex()))
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    lines = [f"private {private}"]
    for needle, count in counts.items():
        lines.append(f"{needle.decode()} {count}")
    for item in samples:
        lines.append(f"{item[0]:#x} {item[1]} {item[2]}")
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
