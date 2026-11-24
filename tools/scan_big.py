# -*- coding: utf-8 -*-
"""Scan every committed page, including large heaps, for decoded resources."""
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
NEEDLES = (b"GT1G0", b"_N1G0", b"_A2G0", b"_A1G0", b"file_encrypt_key", b"WUeq032F")
CHUNK = 8 * 1024 * 1024


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
    counts = {n: 0 for n in NEEDLES}
    samples = []
    addr = 0
    info = MBI()
    scanned = 0
    while True:
        got = k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(info), ctypes.sizeof(info))
        if not got:
            break
        size = info.RegionSize
        readable = info.State == 0x1000 and info.Protect in (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)
        if readable and size > 0:
            offset = 0
            while offset < size:
                step = min(CHUNK, size - offset)
                blob = read(handle, info.BaseAddress + offset, step)
                scanned += len(blob)
                if blob:
                    for needle in NEEDLES:
                        start = 0
                        while counts[needle] < 8:
                            at = blob.find(needle, start)
                            if at < 0:
                                break
                            start = at + 1
                            counts[needle] += 1
                            if len(samples) < 24:
                                abs_at = info.BaseAddress + offset + at
                                window = blob[at:at + 24]
                                samples.append(f"{abs_at:#x} {needle.decode()} {window.hex()}")
                offset += step
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    lines = [f"scanned {scanned}"]
    for needle, count in counts.items():
        lines.append(f"{needle.decode(errors='replace')} {count}")
    lines.extend(samples)
    open(r"D:\Projects\YangHui\DOAXVV\tools\_big.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
