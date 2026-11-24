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
NEEDLES = (b"COMMON\\", b"HIGH\\", b"DX11_data\\", b".g1t", b".g1m", b"TLSK")


def read(handle, addr, size):
    buf = (ctypes.c_char * size)()
    got = ctypes.c_size_t()
    k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
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
    fs = read(handle, base + 0x6C07060, 0x80)
    lines = [f"fs {fs.hex()}"]
    counts = {n: 0 for n in NEEDLES}
    samples = []
    addr = 0
    info = MBI()
    while True:
        got = k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(info), ctypes.sizeof(info))
        if not got:
            break
        size = info.RegionSize
        readable = info.State == 0x1000 and info.Protect in (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)
        in_image = base <= info.BaseAddress < base + 0x8000000
        if readable and size > 0 and not in_image:
            offset = 0
            while offset < size:
                step = min(8 * 1024 * 1024, size - offset)
                blob = read(handle, info.BaseAddress + offset, step)
                if blob:
                    for needle in NEEDLES:
                        if counts[needle] >= 8:
                            continue
                        start = 0
                        while counts[needle] < 8:
                            at = blob.find(needle, start)
                            if at < 0:
                                break
                            start = at + 1
                            counts[needle] += 1
                            window = blob[max(0, at - 24):at + 80]
                            text = "".join(chr(b) if 32 <= b < 127 else "." for b in window)
                            samples.append(f"{info.BaseAddress + offset + at:#x} {text}")
                offset += step
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    for needle, count in counts.items():
        lines.append(f"{needle.decode()} {count}")
    lines.extend(samples)
    open(r"D:\Projects\YangHui\DOAXVV\tools\_open.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
