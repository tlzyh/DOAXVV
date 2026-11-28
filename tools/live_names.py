# -*- coding: utf-8 -*-
"""Collect (resource name, directory key) pairs from the running game, read-only.

  python tools\\live_names.py [--window 256] [--max-region-mb 256]

Opens DOAX_VV.exe with PROCESS_QUERY_INFORMATION | PROCESS_VM_READ only. Every
identifier-like string in readable memory is paired with any u32 within
--window bytes that is a key from out\\archive_dir.csv. Real name/key
structures repeat at one fixed delta, so the summary ranks deltas by count.

Writes out\\live_name_keys.csv (name, encoding, delta, key, type, root, hash)
and out\\live_name_deltas.txt.
"""
import argparse
import collections
import csv
import ctypes
import os
import re
import subprocess
from ctypes import wintypes

import numpy as np

OUT = os.path.join(os.path.dirname(__file__), "..", "out")
DIR_CSV = os.path.join(OUT, "archive_dir.csv")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.CloseHandle.argtypes = [wintypes.HANDLE]


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_uint64), ("AllocationBase", ctypes.c_uint64),
                ("AllocationProtect", wintypes.DWORD), ("_pad1", wintypes.DWORD),
                ("RegionSize", ctypes.c_uint64), ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD), ("_pad2", wintypes.DWORD)]


k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t

READABLE = (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)
ASCII = re.compile(rb"[A-Za-z0-9_][A-Za-z0-9_./\\-]{3,95}\0")
UTF16 = re.compile(rb"(?:[A-Za-z0-9_]\0)(?:[A-Za-z0-9_./\\-]\0){3,95}\0\0")


def find_pid():
    out = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq DOAX_VV.exe", "/FO", "CSV", "/NH"], text=True)
    for row in out.splitlines():
        if "DOAX_VV" in row:
            return int(row.split(",")[1].strip('"'))
    return None


def regions(handle, max_size):
    addr, info = 0, MBI()
    while k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(info), ctypes.sizeof(info)):
        base, size = info.BaseAddress, info.RegionSize
        if info.State == 0x1000 and info.Protect in READABLE and 0 < size <= max_size:
            yield base, size
        if base + size <= addr:
            break
        addr = base + size


def read(handle, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)) or not got.value:
        return None
    return buf.raw[:got.value]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--window", type=int, default=256)
    ap.add_argument("--max-region-mb", type=int, default=256)
    args = ap.parse_args()

    rows = {int(r["key"], 16): r for r in csv.DictReader(open(DIR_CSV, encoding="utf-8"))}
    keys = np.array(sorted(rows), dtype=np.uint32)
    pid = find_pid()
    if pid is None:
        print("DOAX_VV.exe is not running")
        return
    handle = k32.OpenProcess(0x0410, False, pid)
    if not handle:
        print("OpenProcess failed, error", ctypes.get_last_error(), "(run elevated)")
        return
    pairs = collections.Counter()
    scanned = 0
    try:
        for base, size in regions(handle, args.max_region_mb << 20):
            blob = read(handle, base, size)
            if not blob:
                continue
            scanned += len(blob)
            usable = len(blob) & ~3
            words = np.frombuffer(blob, dtype="<u4", count=usable // 4)
            hit = np.nonzero(np.isin(words, keys))[0]
            if not len(hit):
                continue
            hit_pos = hit * 4
            for enc, pattern in (("ascii", ASCII), ("utf16", UTF16)):
                for m in pattern.finditer(blob):
                    lo = np.searchsorted(hit_pos, m.start() - args.window)
                    hi = np.searchsorted(hit_pos, m.start() + args.window)
                    if lo == hi:
                        continue
                    raw = m.group()
                    name = (raw[:-2].decode("utf-16le") if enc == "utf16" else raw[:-1].decode("ascii"))
                    for p in hit_pos[lo:hi]:
                        pairs[(name, enc, int(p) - m.start(), int(words[p // 4]))] += 1
    finally:
        k32.CloseHandle(handle)

    deltas = collections.Counter()
    for (name, enc, delta, key), n in pairs.items():
        deltas[(enc, delta)] += 1
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "live_name_keys.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "encoding", "delta", "key", "type", "root", "hash", "count"])
        for (name, enc, delta, key), n in sorted(pairs.items()):
            r = rows[key]
            w.writerow([name, enc, delta, "%08x" % key, r["type"], r["root"], r["hash"], n])
    with open(os.path.join(OUT, "live_name_deltas.txt"), "w", encoding="utf-8") as fh:
        for (enc, delta), n in deltas.most_common(60):
            fh.write("%s %d %d\n" % (enc, delta, n))
    print("scanned MB", scanned >> 20, "pairs", len(pairs))
    for (enc, delta), n in deltas.most_common(15):
        print(" ", enc, delta, n)


if __name__ == "__main__":
    main()
