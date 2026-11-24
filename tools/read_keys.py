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
    lines = []
    bases = (0xFEFE2330, 0xFF0006D0, 0xFF01E650, 0xFEFC45B8, 0xFEFE2958, 0xFF0008D8)
    for addr in bases:
        blob = read(handle, addr, 0x48)
        if len(blob) < 0x30:
            lines.append(f"{addr:#x} short")
            continue
        state = struct.unpack_from("<I", blob, 0)[0]
        seed = struct.unpack_from("<Q", blob, 8)[0]
        length, stride = struct.unpack_from("<II", blob, 0x10)
        flag = blob[0x18]
        key_len = struct.unpack_from("<Q", blob, 0x20)[0]
        key = blob[0x28:0x28 + min(int(key_len), 16)] if key_len < 32 else blob[0x28:0x38]
        lines.append(
            f"{addr:#x} state {state:#x} seed {seed:#x} len {length:#x} stride {stride} flag {flag} keylen {key_len} key {key.hex()}"
        )
    table = read(handle, base + 0x4003008, 0x40 * 0x100)
    for i in range(0x100):
        rec = table[i * 0x40:(i + 1) * 0x40]
        state = struct.unpack_from("<I", rec, 0x18)[0]
        if state in (1, 2):
            lines.append(f"rec {i} {rec.hex()}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_keys.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
