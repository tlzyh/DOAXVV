# -*- coding: utf-8 -*-
import ctypes
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
    info = MBI()
    k32.VirtualQueryEx(handle, ctypes.c_void_p(0x117E534C8), ctypes.byref(info), ctypes.sizeof(info))
    lines = [f"region {info.BaseAddress:#x} size {info.RegionSize:#x} prot {info.Protect:#x}"]
    model = read(handle, 0x117E534C8 - 32, 256)
    lines.append("model " + model.hex())
    key = read(handle, 0x109BE2DA0 - 64, 256)
    text = "".join(chr(c) if 32 <= c < 127 else "." for c in key)
    lines.append("keyctx " + text)
    # search this region for texture and model magics, but the region may be huge
    needles = (b"GT1G", b"_A2G", b"_A1G", b"G1M", b"SM1G")
    base = info.BaseAddress
    size = min(info.RegionSize, 64 * 1024 * 1024)
    blob = read(handle, base, size)
    for needle in needles:
        at = blob.find(needle)
        lines.append(f"{needle.decode()} {at if at < 0 else hex(base + at)}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_model.txt", "w", encoding="utf-8").write("\n".join(lines))
    open(r"D:\Projects\YangHui\DOAXVV\tools\_model_head.bin", "wb").write(model)


if __name__ == "__main__":
    main()
