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
ADDRS = (0x80E329D0, 0xD0D2F8A0, 0xD07CD1E0, 0xC8A126F0)


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
    lines = []
    for addr in ADDRS:
        blob = read(handle, addr, 0x120)
        lines.append(f"\n{addr:#x}")
        for i in range(0, len(blob), 16):
            dwords = struct.unpack_from("<4I", blob, i) if i + 16 <= len(blob) else ()
            lines.append(f"  +{i:03x} {blob[i:i+16].hex()} {dwords}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_vtx_dump.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
