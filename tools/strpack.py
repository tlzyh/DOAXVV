# -*- coding: utf-8 -*-
"""Dump every STRPACK text pack to out\\strpack.csv.

  python tools\\strpack.py

A STRPACK block holds one "string_pack" child; its entries (offset table at
+0x60) are a u16 line id followed by NUL-terminated UTF-16 text. Lines
contain wait marks such as "w180". Each pack is listed with the database
table 5 row that references it (pkginfo entry 2, see chr_data.py).
"""
import csv
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive_dir  # noqa: E402
from export_gltf import INDEX, read_inflated  # noqa: E402

OUT = archive_dir.OUT
DB_OFFSET = 0x5E2620
TABLE = 5


def db_table(buf, table):
    """Rows of database table `table` as tuples of u32."""
    word = lambda o: struct.unpack_from("<I", buf, DB_OFFSET + o)[0]
    pos = DB_OFFSET + word(0x72C)
    for i in range(table):
        pos += word(0x394 + 4 * i)
    count, size = word(4 * table), word(0x394 + 4 * table)
    stride = size // count
    return [struct.unpack_from("<%dI" % (stride // 4), buf, pos + stride * r) for r in range(count)]


def lines(buf):
    count = struct.unpack_from("<I", buf, 0x14)[0]
    for off in struct.unpack_from("<%dI" % count, buf, 0x60):
        line_id = struct.unpack_from("<H", buf, off)[0]
        end = off + 2
        while buf[end:end + 2] != b"\0\0":
            end += 2
        yield line_id, buf[off + 2:end].decode("utf-16le")


def main():
    root = archive_dir.load_root("COMMON")
    by_hash = {}
    for r in archive_dir.records(root):
        by_hash[r["path"].rpartition("/")[2]] = r["key"]
    refs = {}
    for row in db_table(root, TABLE):
        for v in row:
            refs.setdefault(v, row)
    rows = [r for r in csv.DictReader(open(INDEX, encoding="utf-8")) if r["magic"] == "STRPACK"]
    total = 0
    with open(os.path.join(OUT, "strpack.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["hash", "key", "table5_row", "line", "id", "text"])
        for r in sorted(rows, key=lambda r: r["hash"]):
            key = by_hash.get(r["hash"])
            ref = refs.get(key)
            ref_text = " ".join("%08x" % v for v in ref) if ref else ""
            for n, (line_id, text) in enumerate(lines(read_inflated(r))):
                w.writerow([r["hash"], "%08x" % key if key is not None else "", ref_text, n, line_id, text])
                total += 1
    print("packs", len(rows), "lines", total)


if __name__ == "__main__":
    main()
