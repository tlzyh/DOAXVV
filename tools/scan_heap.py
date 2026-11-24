# -*- coding: utf-8 -*-
"""Search the game's large private heaps for decoded resources."""
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
TARGETS = (
    (0x80000000, 3391 * 1024 * 1024),
    (0x160000000, 971 * 1024 * 1024),
)
NEEDLES = (b"TLSK", b"TMC\x00", b"DDS ", b"WGT_body", b"MOT00_Hips", b"\x4a\x7b")
OUT = r"D:\Projects\YangHui\DOAXVV\tools\_heap.txt"


def read(handle, addr, size):
    buf = (ctypes.c_char * size)()
    got = ctypes.c_size_t()
    k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    return bytes(buf[:got.value])


def main():
    import subprocess
    text = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq DOAX_VV.exe", "/FO", "CSV", "/NH"], text=True
    )
    pid = int(next(row.split(",")[1].strip('"') for row in text.splitlines() if "DOAX_VV" in row))
    handle = k32.OpenProcess(0x0410, False, pid)
    counts = {needle: 0 for needle in NEEDLES}
    samples = []
    float_pages = 0
    pages = 0
    for base, size in TARGETS:
        offset = 0
        while offset < size:
            step = min(8 * 1024 * 1024, size - offset)
            blob = read(handle, base + offset, step)
            pages += 1
            if blob:
                for needle in NEEDLES:
                    counts[needle] += blob.count(needle)
                    if len(samples) < 12 and needle != b"\x4a\x7b":
                        at = blob.find(needle)
                        if at >= 0:
                            samples.append(f"{base+offset+at:#x} {needle!r} {blob[at:at+24].hex()}")
                # one float-likeness sample per 8MB
                if len(blob) >= 4096:
                    good = 0
                    for i in range(0, 4096, 4):
                        value = struct.unpack_from("<f", blob, i)[0]
                        if value == value and abs(value) < 4:
                            good += 1
                    if good > 700:
                        float_pages += 1
            offset += step
    lines = [f"pid {pid}", f"pages {pages}", f"floatish pages {float_pages}"]
    for needle, count in counts.items():
        lines.append(f"{needle!r} {count}")
    lines.extend(samples)
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
