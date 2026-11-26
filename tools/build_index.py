# -*- coding: utf-8 -*-
"""Write index.csv: one row per hash file with its cipher mode, key and type.

Modes:
  page   zlib pages under the short key of the inflated size
  raw    whole file under the short key of the file size (ASF, BIN2)
  plain  stored as is (ASF, _L1G, 80-byte records, small UI tables)
"""
import collections
import csv
import multiprocessing
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from decrypt import decrypt, first_page, key_from_index, magic_of, recover_key, sizes_for_key

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
OUT = r"D:\Projects\YangHui\DOAXVV\index.csv"
FOLDERS = ("COMMON", "HIGH", os.path.join("DL", "COMMON"), os.path.join("DL", "HIGH"))
ASF = bytes.fromhex("3026b2758e66cf11a6d900aa0062ce6c")
RAW_MAGICS = {ASF: "ASF", b"BIN2": "BIN2"}
PLAIN_MAGICS = {ASF: "ASF", b"_L1G": "G1L"}
RECORD80 = bytes.fromhex("1ca2000041d848c7")
SAMPLE = 65536
COLUMNS = ("folder", "hash", "size", "cipher_pair", "mode", "key", "plain_size", "magic", "name")


def resource_name(blob):
    if not blob:
        return ""
    found = []
    for match in re.finditer(rb"[ -~]{4,}", blob[:8000]):
        text = match.group().decode("ascii")
        if any(ch.isalpha() for ch in text) and not text.startswith("????"):
            found.append(text)
        if len(found) >= 4:
            break
    for text in found:
        if text not in ("TLSK3100", "CONTE", "SCENE", "ColorLis", "tdpack", "char_dat", "TMC"):
            return text
    return found[0] if found else ""


def plain_size_of(key, page):
    sizes = sizes_for_key(key)
    if len(page) >= 8:
        total = int.from_bytes(page[4:8], "little")
        if total in sizes:
            return total
    return sizes[0] if len(sizes) == 1 else ""


def classify(full, size, hints):
    with open(full, "rb") as handle:
        sample = handle.read(SAMPLE)
    for magic, label in PLAIN_MAGICS.items():
        if sample.startswith(magic):
            return "plain", "", "", label, ""
    if size == 80 and sample.startswith(RECORD80):
        return "plain", "", "", "record80", ""
    key = recover_key(sample, hints, reader=lambda: open(full, "rb").read())
    if key:
        page = first_page(sample, key)
        plain_size = plain_size_of(key, page)
        return "page", key, plain_size, magic_of(page, plain_size or None), resource_name(page)
    raw_key = key_from_index(size)
    head = decrypt(sample[:16], raw_key)
    for magic, label in RAW_MAGICS.items():
        if head.startswith(magic[:len(head)]) and len(head) >= 4:
            return "raw", raw_key, size, label, ""
    small_table = size < 4096 and sample.startswith(b"\x00\x00\x00\x00") and sample[5:8] == b"\x00\x00\x00"
    if small_table or len(re.findall(rb"[A-Za-z_][A-Za-z0-9_]{5,}", sample[:4096])) >= 3:
        return "plain", "", "", "table", resource_name(sample)
    return "", "", "", "", ""


def work(task):
    rel, pair, items = task
    hints = collections.deque(maxlen=4)
    rows = []
    for name, size in items:
        full = os.path.join(ROOT, rel, name)
        if size < 16:
            rows.append((rel, name, size, pair, "", "", "", "tiny", ""))
            continue
        mode, key, plain_size, magic, label = classify(full, size, list(hints))
        if mode == "page" and key not in hints:
            hints.appendleft(key)
        rows.append((rel, name, size, pair, mode, key.hex() if key else "", plain_size, magic, label))
    return rows


def tasks():
    grouped = collections.defaultdict(list)
    for rel in FOLDERS:
        folder = os.path.join(ROOT, rel)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            size = os.path.getsize(full)
            with open(full, "rb") as handle:
                head = handle.read(6)
            grouped[(rel, head[4:6].hex() if len(head) >= 6 else "")].append((name, size))
    out = []
    for (rel, pair), items in grouped.items():
        for start in range(0, len(items), 64):
            out.append((rel, pair, items[start:start + 64]))
    out.sort(key=lambda task: -sum(size for _name, size in task[2]))
    return out


def main():
    jobs = tasks()
    print("tasks", len(jobs), flush=True)
    rows = []
    with multiprocessing.Pool() as pool:
        for done, chunk in enumerate(pool.imap_unordered(work, jobs), 1):
            rows.extend(chunk)
            if done % 50 == 0:
                print("tasks", done, "rows", len(rows), flush=True)
    rows.sort(key=lambda item: (item[0], item[1]))
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    modes = collections.Counter(row[4] or "unknown" for row in rows)
    kinds = collections.Counter(row[7] for row in rows if row[4])
    print("wrote", OUT, "rows", len(rows), dict(modes))
    print("kinds", kinds.most_common(20))


if __name__ == "__main__":
    main()
