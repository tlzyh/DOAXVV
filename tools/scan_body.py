# -*- coding: utf-8 -*-
"""Look for a loaded body mesh or texture while the character is on screen."""
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
MAGICS = (b"GT1G", b"_N1G", b"_A2G", b"_A1G", b"_M1G", b"DDS ", b"G1M_")
NAMES = (b"n_hara", b"n_kubi", b"j_kosi", b"swimsuit", b"Bip01", b"body_00")


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
    counts = {item: 0 for item in MAGICS + NAMES}
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
                    for item in MAGICS + NAMES:
                        if counts[item] >= 6:
                            continue
                        start = 0
                        while counts[item] < 6:
                            at = blob.find(item, start)
                            if at < 0:
                                break
                            start = at + 1
                            counts[item] += 1
                            sample = blob[at:at + 24]
                            size_field = struct.unpack_from("<I", sample, 8)[0] if len(sample) >= 12 else 0
                            samples.append(
                                f"{info.BaseAddress + offset + at:#x} {item.decode(errors='replace')} "
                                f"field {size_field:#x} {sample.hex()}"
                            )
                offset += step
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    lines = [f"pid {pid} base {base:#x}"]
    for item, count in counts.items():
        lines.append(f"{item.decode(errors='replace')} {count}")
    lines.extend(samples)
    open(r"D:\Projects\YangHui\DOAXVV\tools\_body.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
