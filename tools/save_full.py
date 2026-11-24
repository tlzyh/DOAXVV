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


def main():
    import subprocess
    out = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq DOAX_VV.exe", "/FO", "CSV", "/NH"], text=True
    )
    pid = int(next(row.split(",")[1].strip('"') for row in out.splitlines() if "DOAX_VV" in row))
    handle = k32.OpenProcess(0x0410, False, pid)
    head = (ctypes.c_char * 16)()
    got = ctypes.c_size_t()
    k32.ReadProcessMemory(handle, ctypes.c_void_p(0x117E534C8), head, 16, ctypes.byref(got))
    size = struct.unpack_from("<I", bytes(head), 8)[0]
    note = [f"head {bytes(head).hex()} size {size}"]
    if 0x20 < size < 32 * 1024 * 1024:
        buf = (ctypes.c_char * size)()
        ok = k32.ReadProcessMemory(handle, ctypes.c_void_p(0x117E534C8), buf, size, ctypes.byref(got))
        data = bytes(buf[:got.value])
        open(r"D:\Projects\YangHui\DOAXVV\tools\_n1g_full.bin", "wb").write(data)
        note.append(f"wrote {len(data)} ok {ok}")
        for magic in (b"GT1G", b"_A2G", b"_A1G", b"BON", b"VTX"):
            note.append(f"{magic.decode(errors='replace')} {data.find(magic)}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_n1g_full.txt", "w").write("\n".join(note))


if __name__ == "__main__":
    main()
