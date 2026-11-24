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
    ptr = struct.unpack("<Q", read(handle, base + 0x4006728, 8))[0]
    needle = struct.pack("<Q", ptr)
    keys = []
    addr = 0
    info = MBI()
    while True:
        got = k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(info), ctypes.sizeof(info))
        if not got:
            break
        size = info.RegionSize
        readable = info.State == 0x1000 and info.Protect in (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)
        if readable and size > 0:
            offset = 0
            while offset < size:
                step = min(8 * 1024 * 1024, size - offset)
                blob = read(handle, info.BaseAddress + offset, step)
                start = 0
                while blob:
                    at = blob.find(needle, start)
                    if at < 0:
                        break
                    start = at + 8
                    abs_at = info.BaseAddress + offset + at
                    if abs_at == base + 0x4006728 or at < 8:
                        continue
                    state = struct.unpack_from("<I", blob, at - 8)[0]
                    if at + 0x28 > len(blob):
                        continue
                    length, stride = struct.unpack_from("<II", blob, at + 8)
                    flag = blob[at + 0x10]
                    key_len = struct.unpack_from("<Q", blob, at + 0x18)[0]
                    if length == 0x158 and stride == 1 and flag == 1 and 0 < key_len <= 8:
                        key = blob[at + 0x20:at + 0x20 + key_len]
                        keys.append((abs_at - 8, state, key))
                offset += step
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    lines = []
    seen = set()
    for addr, state, key in keys:
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"{addr:#x} state {state:#x} {key.hex()}")
    lines.append(f"unique {len(seen)} raw {len(keys)}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_allkeys.txt", "w").write("\n".join(lines))


if __name__ == "__main__":
    main()
