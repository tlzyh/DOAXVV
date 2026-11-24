# -*- coding: utf-8 -*-
"""Write index.csv: hash, folder, size, key, magic and resource name."""
import collections
import csv
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(__file__))
from decrypt import SEED, decrypt, first_page, magic_of

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
OUT = r"D:\Projects\YangHui\DOAXVV\index.csv"
ASF = bytes.fromhex("3026b2758e66cf11")


def mixed_for(cipher, plain):
    if cipher == 0:
        return None if plain else 0
    return 0 if plain == cipher else cipher ^ plain


def probe(sample, key):
    plain = decrypt(sample[:64], key)
    if plain[4] != 0x78 or plain[5] not in (0x9C, 0xDA):
        return False
    try:
        zlib.decompress(plain[4:])
        return True
    except zlib.error as exc:
        text = str(exc)
        return "incomplete" in text or "truncated" in text


def recover(sample, pair):
    for plain5 in (0x9C, 0xDA):
        m4 = mixed_for(pair[0], 0x78)
        m5 = mixed_for(pair[1], plain5)
        if m4 is None or m5 is None:
            continue
        k1 = SEED[4] ^ m4
        k2 = SEED[5] ^ m5
        keys = [bytes((k1, k2))]
        keys.extend(bytes((b0, k1, k2)) for b0 in range(256))
        for key in keys:
            if not probe(sample, key):
                continue
            if first_page(sample, key):
                return key
    return None


def resource_name(blob):
    if not blob:
        return ""
    cur = bytearray()
    found = []
    for value in blob[:8000]:
        if 32 <= value < 127:
            cur.append(value)
        else:
            if len(cur) >= 4 and any(chr(b).isalpha() for b in cur):
                text = cur.decode("ascii")
                if any(ch.isalnum() for ch in text) and not text.startswith("????"):
                    found.append(text)
            cur.clear()
            if len(found) >= 4:
                break
    for text in found:
        if text not in ("TLSK3100", "CONTE", "SCENE", "ColorLis", "tdpack", "char_dat"):
            return text
    return found[0] if found else ""


def main():
    folders = ("COMMON", "HIGH", os.path.join("DL", "COMMON"), os.path.join("DL", "HIGH"))
    rows = []
    grouped = collections.defaultdict(list)
    for rel in folders:
        folder = os.path.join(ROOT, rel)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size < 16:
                rows.append((rel, name, size, "", "", "tiny", ""))
                continue
            head = open(full, "rb").read(6)
            if head.startswith(ASF):
                rows.append((rel, name, size, "", "", "ASF", ""))
                continue
            if size == 80:
                rows.append((rel, name, size, "", "", "record80", ""))
                continue
            grouped[(rel, bytes(head[4:6]))].append((name, full, size))
    print("groups", len(grouped), "early", len(rows), flush=True)
    done = 0
    for (rel, pair), items in grouped.items():
        sample_path = items[0][1]
        sample = open(sample_path, "rb").read(min(items[0][2], 20000))
        key = recover(sample, pair)
        key_hex = key.hex() if key else ""
        for name, full, size in items:
            magic = ""
            label = ""
            if key:
                blob = open(full, "rb").read(min(size, 16000))
                page = first_page(blob, key)
                magic = magic_of(page)
                label = resource_name(page)
            rows.append((rel, name, size, pair.hex(), key_hex, magic, label))
        done += 1
        if done % 200 == 0:
            print("groups", done, "rows", len(rows), flush=True)
    rows.sort(key=lambda item: (item[0], item[1]))
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("folder", "hash", "size", "cipher_pair", "key", "magic", "name"))
        writer.writerows(rows)
    named = sum(1 for row in rows if row[5] and row[5] not in ("tiny", "ASF", "record80", ""))
    print("wrote", OUT, "rows", len(rows), "identified", named)


if __name__ == "__main__":
    main()
