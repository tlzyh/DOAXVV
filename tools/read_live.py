# -*- coding: utf-8 -*-
"""Read the cipher seed and any already-decoded resource headers from DOAX_VV."""
import ctypes
import struct
from ctypes import wintypes

OUT = r"D:\Projects\YangHui\DOAXVV\tools\_live_report.txt"
SEED_PATH = r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin"
PTR_RVA = 0x4003838
LEN_RVA = 0x4003830
MAGICS = (b"GT1G", b"_N1G", b"_M1G", b"_A2G", b"_A1G", b"OC1G")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
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

lines = []


def log(text):
    print(text)
    lines.append(text)


def read(handle, addr, size):
    buf = (ctypes.c_char * size)()
    got = ctypes.c_size_t()
    ok = k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    if not ok or got.value == 0:
        return None
    return bytes(buf[:got.value])


def main():
    import subprocess
    out = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq DOAX_VV.exe", "/FO", "CSV", "/NH"],
        text=True,
    )
    pid = None
    for row in out.splitlines():
        if "DOAX_VV" in row:
            pid = int(row.split(",")[1].strip('"'))
            break
    if pid is None:
        log("no DOAX_VV")
        return
    log(f"pid {pid}")
    handle = k32.OpenProcess(0x0410, False, pid)
    log(f"open {handle} err {ctypes.get_last_error()}")
    if not handle:
        return
    mods = (ctypes.c_void_p * 8)()
    needed = wintypes.DWORD()
    psapi.EnumProcessModules(handle, mods, ctypes.sizeof(mods), ctypes.byref(needed))
    base = mods[0] or 0
    log(f"base {base:#x}")
    length = read(handle, base + LEN_RVA, 4)
    raw = read(handle, base + PTR_RVA, 8)
    log(f"len field {length.hex() if length else None}")
    log(f"ptr field {raw.hex() if raw else None}")
    if raw and len(raw) == 8:
        ptr = struct.unpack("<Q", raw)[0]
        if ptr:
            seed = read(handle, ptr, 0x158)
            if seed:
                open(SEED_PATH, "wb").write(seed)
                log(f"seed {seed[:32].hex()} len {len(seed)}")
    hits = []
    addr = 0
    info = MBI()
    scanned = 0
    while True:
        got = k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(info), ctypes.sizeof(info))
        if not got:
            break
        size = info.RegionSize
        readable = info.State == 0x1000 and info.Protect in (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)
        if readable and 0 < size <= 64 * 1024 * 1024:
            blob = read(handle, info.BaseAddress, size)
            if blob:
                scanned += len(blob)
                for magic in MAGICS:
                    start = 0
                    while len(hits) < 30:
                        at = blob.find(magic, start)
                        if at < 0:
                            break
                        start = at + 1
                        sample = blob[max(0, at - 8):at + 24]
                        hits.append((info.BaseAddress + at, magic, sample))
        next_addr = info.BaseAddress + size
        if next_addr <= addr:
            break
        addr = next_addr
    log(f"scanned {scanned} hits {len(hits)}")
    for at, magic, sample in hits:
        log(f"{at:#x} {magic.decode()} {sample.hex()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"error {type(exc).__name__}: {exc}")
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
