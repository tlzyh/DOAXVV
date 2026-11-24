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
        return None
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
    lines = [f"base {base:#x} pid {pid} handle {handle}"]
    if not handle:
        lines.append(f"open failed {ctypes.get_last_error()}")
    blob = read(handle, base + 0x400CDE0, 0x40 * 0x100) if handle else None
    lines.append("slots")
    shown = 0
    if blob:
        for i in range(0x100):
            rec = blob[i * 0x40:(i + 1) * 0x40]
            if rec[:0x1c] == b"\x00" * 0x1c and rec[0x1e:] == b"\x00" * (0x40 - 0x1e):
                continue
            q = struct.unpack_from("<4Q", rec)
            lines.append(f"{i} {[hex(x) for x in q]} flag {rec[0x1c:0x20].hex()}")
            shown += 1
            if shown > 40:
                break
    lines.append(f"slot-shown {shown}")
    table = read(handle, base + 0x4011BE8, 0x40 * 0x100) if handle else None
    lines.append("open-table")
    active = 0
    if table:
        for i in range(0x100):
            rec = table[i * 0x40:(i + 1) * 0x40]
            if rec == b"\x00" * 0x40:
                continue
            index, second = struct.unpack_from("<QQ", rec)
            ident = struct.unpack_from("<I", rec, 0x10)[0]
            state = struct.unpack_from("<I", rec, 0x18)[0]
            lines.append(f"{i} state {state:#x} index {index:#x} second {second:#x} id {ident:#x}")
            active += 1
            if active > 40:
                break
    lines.append(f"open-shown {active}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_slots.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
