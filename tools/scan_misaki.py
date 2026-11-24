# -*- coding: utf-8 -*-
"""Find Misaki's loaded mesh, textures, and any new cipher keys."""
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
NEEDLES = (
    b"misaki", b"Misaki", b"MISAKI", b"mis_body", b"mis_hair",
    b"character_pic_mis", b"GT1G0", b"_N1G0000", b"DDS ",
)


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
    needle = struct.pack("<Q", ptr) if ptr else b""
    counts = {item: 0 for item in NEEDLES}
    samples = []
    keys = []
    addr = 0
    info = MBI()
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
                    for item in NEEDLES:
                        if counts[item] >= 8:
                            continue
                        start = 0
                        while counts[item] < 8:
                            at = blob.find(item, start)
                            if at < 0:
                                break
                            start = at + 1
                            if item == b"DDS " and len(blob) >= at + 20:
                                height, width = struct.unpack_from("<II", blob, at + 12)
                                if width < 64 or height < 64:
                                    continue
                            counts[item] += 1
                            window = blob[max(0, at - 8):at + 48]
                            text = "".join(chr(b) if 32 <= b < 127 else "." for b in window)
                            samples.append(f"{info.BaseAddress + offset + at:#x} {item.decode()} {text}")
                    if needle:
                        start = 0
                        while len(keys) < 12:
                            at = blob.find(needle, start)
                            if at < 0:
                                break
                            start = at + 8
                            if at < 8 or at + 0x28 > len(blob):
                                continue
                            length, stride = struct.unpack_from("<II", blob, at + 8)
                            flag = blob[at + 0x10]
                            key_len = struct.unpack_from("<Q", blob, at + 0x18)[0]
                            if length == 0x158 and stride == 1 and flag == 1 and 0 < key_len <= 8:
                                key = blob[at + 0x20:at + 0x20 + key_len]
                                keys.append(key)
                offset += step
        nxt = info.BaseAddress + size
        if nxt <= addr:
            break
        addr = nxt
    lines = [f"pid {pid}"]
    for item, count in counts.items():
        lines.append(f"{item.decode()} {count}")
    uniq = []
    seen = set()
    for key in keys:
        if key not in seen:
            seen.add(key)
            uniq.append(key.hex())
    lines.append("keys " + " ".join(uniq))
    lines.extend(samples)
    open(r"D:\Projects\YangHui\DOAXVV\tools\_misaki.txt", "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
