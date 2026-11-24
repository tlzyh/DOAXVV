# -*- coding: utf-8 -*-
"""Test the u16 chunk chain used by the mode-7 reader."""
import os

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"


def chunk_size(word):
    return ((word & 0x7FFF) + 0x13) & ~0xF


def walk(data):
    pos = 0
    count = 0
    while pos + 2 <= len(data):
        word = int.from_bytes(data[pos:pos + 2], "little")
        size = chunk_size(word)
        if size < 16 or pos + size > len(data):
            return count, pos, False
        pos += size
        count += 1
        if count > 100000:
            return count, pos, False
    return count, pos, pos == len(data)


def main():
    rows = []
    for folder in ("COMMON", "HIGH"):
        folder_path = os.path.join(ROOT, folder)
        taken = 0
        for name in os.listdir(folder_path):
            full = os.path.join(folder_path, name)
            size = os.path.getsize(full)
            if size < 32:
                continue
            with open(full, "rb") as handle:
                data = handle.read(min(size, 256 * 1024))
            # Only judge files that fit in the sample, or whose first chunks stay inside it.
            count, pos, exact = walk(data if size <= len(data) else data)
            if size <= len(data):
                rows.append((exact, count, pos, size, folder, name[:12], data[:8].hex()))
            taken += 1
            if taken >= 400:
                break
    good = [row for row in rows if row[0]]
    print("tested", len(rows), "exact", len(good))
    for row in good[:15]:
        print(" GOOD", row)
    print("--- misses ---")
    for row in rows[:8]:
        if not row[0]:
            print(" MISS", row)


if __name__ == "__main__":
    main()
