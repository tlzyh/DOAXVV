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
    ptr = struct.unpack("<Q", read(handle, base + 0x4006728, 8))[0]
    needle = struct.pack("<Q", ptr)
    lines = [f"ptr {ptr:#x}"]
    addr = 0
    info = MBI()
    found = 0
    magics = {b"GT1G0": 0, b"_N1G0": 0, b"_A2G0": 0}
    samples = []
    while found < 12:
        got = k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(info), ctypes.sizeof(info))
        if not got:
            break
        size = info.RegionSize
        readable = info.State == 0x1000 and info.Protect in (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)
        if readable and 0 < size <= 256 * 1024 * 1024:
            offset = 0
            while offset < size and found < 12:
                step = min(8 * 1024 * 1024, size - offset)
                blob = read(handle, info.BaseAddress + offset, step)
                if blob:
                    start = 0
                    while found < 12:
                        at = blob.find(needle, start)
                        if at < 0:
                            break
                        start = at + 8
                        abs_at = info.BaseAddress + offset + at
                        window = blob[max(0, at - 16):at + 40]
                        lines.append(f"{abs_at:#x} {window.hex()}")
                        found += 1
                    for magic in magics:
                        if magics[magic] >= 4:
                            continue
                        start = 0
                        while magics[magic] < 4:
                            at = blob.find(magic, start)
                            if at < 0:
                                break
                            start = at + 1
                            magics[magic] += 1
                            samples.append(f"{info.BaseAddress + offset + at:#x} {magic.decode()} {blob[at:at+16].hex()}")
                offset += step
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    lines.append(f"ptr hits {found}")
    for magic, count in magics.items():
        lines.append(f"{magic.decode()} {count}")
    lines.extend(samples)
    open(r"D:\Projects\YangHui\DOAXVV\tools\_ctx2.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
