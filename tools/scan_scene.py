# -*- coding: utf-8 -*-
"""Find decoded models and open archive records in the running game."""
import ctypes
import struct
from ctypes import wintypes

OUT = r"D:\Projects\YangHui\DOAXVV\tools\_scene.txt"
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
MAGICS = (b"GT1G0", b"_N1G0", b"_A2G0", b"_A1G0")


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
    lines = [f"pid {pid} base {base:#x}"]
    ptr = struct.unpack("<Q", read(handle, base + 0x4006728, 8))[0]
    lines.append(f"seed {ptr:#x}")
    needle = struct.pack("<Q", ptr) if ptr else b""
    table = read(handle, base + 0x4003008, 0x40 * 0x100)
    opened = 0
    for i in range(0x100):
        rec = table[i * 0x40:(i + 1) * 0x40]
        if len(rec) < 0x40:
            break
        state = struct.unpack_from("<I", rec, 0x18)[0]
        if state in (1, 2):
            index = struct.unpack_from("<Q", rec, 0)[0]
            ident = struct.unpack_from("<I", rec, 0x10)[0]
            lines.append(f"arch {i} state {state} index {index:#x} id {ident:#x}")
            opened += 1
    lines.append(f"opened {opened}")
    counts = {m: 0 for m in MAGICS}
    ctx = 0
    addr = 0
    info = MBI()
    hits = []
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
                    if needle and ctx < 6:
                        start = 0
                        while ctx < 6:
                            at = blob.find(needle, start)
                            if at < 0:
                                break
                            start = at + 8
                            abs_at = info.BaseAddress + offset + at
                            if abs_at != base + 0x4006728:
                                hits.append(f"ctx {abs_at:#x} {blob[max(0, at-16):at+32].hex()}")
                                ctx += 1
                    for magic in MAGICS:
                        if counts[magic] >= 8:
                            continue
                        start = 0
                        while counts[magic] < 8:
                            at = blob.find(magic, start)
                            if at < 0:
                                break
                            start = at + 1
                            counts[magic] += 1
                            sample = blob[at:at + 32]
                            size_field = struct.unpack_from("<I", sample, 8)[0] if len(sample) >= 12 else 0
                            hits.append(f"{info.BaseAddress + offset + at:#x} {magic.decode()} size {size_field:#x} {sample.hex()}")
                offset += step
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    for magic, count in counts.items():
        lines.append(f"{magic.decode()} {count}")
    lines.append(f"contexts {ctx}")
    lines.extend(hits)
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
