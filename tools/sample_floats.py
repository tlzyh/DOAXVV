# -*- coding: utf-8 -*-
"""Look for a body-shaped float stream in the large CPU heap."""
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
BASE = 0x80000000
SPAN = 512 * 1024 * 1024


def read(handle, addr, size):
    buf = (ctypes.c_char * size)()
    got = ctypes.c_size_t()
    k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    return bytes(buf[:got.value])


def consider(blob, addr):
    best = None
    for stride in (12, 32, 48, 80):
        xs, ys, zs = [], [], []
        for i in range(0, min(len(blob) - 12, stride * 400), stride):
            x, y, z = struct.unpack_from("<fff", blob, i)
            if x != x or abs(x) > 3 or abs(y) > 3 or abs(z) > 3:
                xs, ys, zs = [], [], []
                continue
            xs.append(x)
            ys.append(y)
            zs.append(z)
            if len(xs) == 200:
                span_y = max(ys) - min(ys)
                span_x = max(xs) - min(xs)
                mags = sorted((a * a + b * b + c * c) ** 0.5 for a, b, c in zip(xs, ys, zs))
                med = mags[100]
                if span_y > 0.8 and span_x > 0.2 and med < 0.9:
                    score = span_y
                    if best is None or score > best[0]:
                        best = (score, addr, stride, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
                xs, ys, zs = [], [], []
    return best


def main():
    import subprocess
    text = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq DOAX_VV.exe", "/FO", "CSV", "/NH"], text=True
    )
    pid = int(next(row.split(",")[1].strip('"') for row in text.splitlines() if "DOAX_VV" in row))
    handle = k32.OpenProcess(0x0410, False, pid)
    best = None
    offset = 0
    while offset < SPAN:
        blob = read(handle, BASE + offset, 256 * 1024)
        found = consider(blob, BASE + offset) if blob else None
        if found and (best is None or found[0] > best[0]):
            best = found
        offset += 1024 * 1024
    lines = ["none" if best is None else " ".join(str(round(v, 3) if isinstance(v, float) else hex(v) if isinstance(v, int) and v > 255 else v) for v in best)]
    open(r"D:\Projects\YangHui\DOAXVV\tools\_float_sample.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
