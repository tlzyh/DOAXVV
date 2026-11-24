# -*- coding: utf-8 -*-
"""Read the current cipher seed and any decoded resource headers."""
import ctypes
import struct
from ctypes import wintypes

OUT = r"D:\Projects\YangHui\DOAXVV\tools\_now.txt"
SEED_PATH = r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin"
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
NEEDLES = (b"GT1G0", b"_N1G0", b"_A2G0", b"_A1G0", b"file_encrypt_key")


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
    lines = [f"pid {pid} open {bool(handle)} err {ctypes.get_last_error()}"]
    if not handle:
        open(OUT, "w", encoding="utf-8").write("\n".join(lines))
        return
    psapi = ctypes.WinDLL("psapi")
    mods = (ctypes.c_void_p * 4)()
    needed = wintypes.DWORD()
    psapi.EnumProcessModules(handle, mods, ctypes.sizeof(mods), ctypes.byref(needed))
    base = mods[0]
    raw_ptr = read(handle, base + 0x4003838, 8)
    raw_len = read(handle, base + 0x4003830, 4)
    ptr = struct.unpack("<Q", raw_ptr)[0] if len(raw_ptr) == 8 else 0
    length = struct.unpack("<I", raw_len)[0] if len(raw_len) == 4 else 0
    lines.append(f"base {base:#x} ptr {ptr:#x} len {length:#x}")
    if ptr and 0 < length <= 4096:
        seed = read(handle, ptr, length)
        open(SEED_PATH, "wb").write(seed)
        lines.append(f"seed {seed[:48]!r}")
        needle = struct.pack("<Q", ptr)
    else:
        needle = b""
    counts = {n: 0 for n in NEEDLES}
    ctx = 0
    addr = 0
    info = MBI()
    samples = []
    while True:
        got = k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(info), ctypes.sizeof(info))
        if not got:
            break
        size = info.RegionSize
        readable = info.State == 0x1000 and info.Protect in (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)
        if readable and 0 < size <= 256 * 1024 * 1024:
            offset = 0
            while offset < size:
                step = min(8 * 1024 * 1024, size - offset)
                blob = read(handle, info.BaseAddress + offset, step)
                if blob and needle and ctx < 8:
                    start = 0
                    while ctx < 8:
                        at = blob.find(needle, start)
                        if at < 0:
                            break
                        start = at + 8
                        abs_at = info.BaseAddress + offset + at
                        if abs_at != base + 0x4003838:
                            window = blob[max(0, at - 16):at + 48]
                            samples.append(f"ctx {abs_at:#x} {window.hex()}")
                            ctx += 1
                if blob:
                    for magic in NEEDLES:
                        if counts[magic] >= 6:
                            continue
                        start = 0
                        while counts[magic] < 6:
                            at = blob.find(magic, start)
                            if at < 0:
                                break
                            start = at + 1
                            counts[magic] += 1
                            samples.append(
                                f"{info.BaseAddress + offset + at:#x} {magic.decode()} {blob[at:at+24].hex()}"
                            )
                offset += step
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    for magic, count in counts.items():
        lines.append(f"{magic.decode()} {count}")
    lines.append(f"contexts {ctx}")
    lines.extend(samples)
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
