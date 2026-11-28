# -*- coding: utf-8 -*-
"""Dump the game's character database (pkginfo entry 2, block "chr_data").

  python tools\\chr_data.py

chr_data has one child block per section (chrall, cos, mot, hair, scale,
equip, facial, flush, skeleton, itemoffs, ...). Each section holds one block
per character (the first is a shared header) whose entries are fixed-size
rows of u32 words. Words that are keys in out\\archive_dir.csv are resolved to
"type:folder/hash".

Writes
  out\\chr_data\\<section>.csv     section, char block, row, id, then every word
                                   (resolved keys as type:FOLDER/hash)
  out\\chr_motion_sets.csv         one row per mot entry: id and the char_dat
                                   banks it plays together, labelled body /
                                   face / hand / breast / root from motions.csv
  out\\tmc_pairs.csv               every TMC key followed by its TMCL key anywhere
                                   in the database (types 17/18, 19/20, 23/24,
                                   25/26, 27/28, 39/40, 53/54, 80/81)
  out\\chr_characters.csv          one row per chrall entry: character id
                                   (low 16 bits of every id), code from the body
                                   TMC name (chr_mis -> mis), body and face TMC

Row ids are (number << 16) | character id, e.g. mot 0x00e9000b is motion
0xe9 of character 0x0b (mis).
"""
import collections
import csv
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import archive_dir  # noqa: E402

OUT = archive_dir.OUT
DB_ENTRY = 2


def is_block(buf, pos):
    return (pos + 0x30 <= len(buf) and buf[pos + 10:pos + 12] == b"\x01\x01"
            and struct.unpack_from("<I", buf, pos + 12)[0] == 0x30
            and re.fullmatch(rb"[A-Za-z0-9_]+\0*", buf[pos:pos + 8]) is not None)


def block_name(buf, pos):
    return buf[pos:pos + 8].rstrip(b"\0").decode()


def children(buf, pos):
    count = struct.unpack_from("<I", buf, pos + 0x14)[0]
    return [pos + o for o in struct.unpack_from("<%dI" % count, buf, pos + 0x30) if o]


def child_spans(buf, pos):
    """(start, end) of every child entry; the last one ends with the block."""
    size = struct.unpack_from("<I", buf, pos + 0x10)[0]
    starts = children(buf, pos)
    return list(zip(starts, starts[1:] + [pos + size]))


def find_chr_data(buf):
    pos = buf.find(b"chr_data\0\0\x01\x01")
    if pos < 0 or not is_block(buf, pos):
        raise ValueError("no chr_data block")
    return pos


def motion_kinds():
    """char_dat hash -> kind of its first multi-node bank (body, face, hand, breast, root)."""
    path = os.path.join(OUT, "motions.csv")
    kinds = {}
    if not os.path.exists(path):
        return kinds
    for r in csv.DictReader(open(path, encoding="utf-8")):
        name = r["name"]
        if name.startswith("MOT00_Hips"):
            kind = "body"
        elif name.startswith("OPT_Face"):
            kind = "face"
        elif name.startswith("OPT_Hand"):
            kind = "hand"
        elif name.startswith("OPT_Breast"):
            kind = "breast"
        elif name == "MOT00":
            kind = "root"
        else:
            continue
        kinds.setdefault(r["hash"], kind)
    return kinds


TMC_TYPES = {17: 18, 19: 20, 23: 24, 25: 26, 27: 28, 39: 40, 53: 54, 80: 81}
DB_START = 0x5E2620


def write_tmc_pairs(buf, keys):
    """TMC -> TMCL wherever a TMC key is immediately followed by a TMCL key of the matching type."""
    start = DB_START
    end = buf.find(b"label\0\0\0", start)
    words = struct.unpack_from("<%dI" % ((end - start) // 4), buf, start)
    pairs = {}
    for a, b in zip(words, words[1:]):
        if a in keys and b in keys and TMC_TYPES.get(keys[a][0]) == keys[b][0]:
            pairs.setdefault(keys[a][1].rpartition("/")[2], set()).add(keys[b][1].rpartition("/")[2])
    with open(os.path.join(OUT, "tmc_pairs.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["tmc", "tmcl"])
        for tmc, tmcls in sorted(pairs.items()):
            for tmcl in sorted(tmcls):
                w.writerow([tmc, tmcl])
    print("tmc pairs", len(pairs), "with several tmcl", sum(len(v) > 1 for v in pairs.values()))


def tmc_names():
    path = os.path.join(OUT, "models", "pairing.csv")
    if not os.path.exists(path):
        return {}
    return {r["tmc_hash"]: r["name"] for r in csv.DictReader(open(path, encoding="utf-8"))}


def write_characters(buf, chrall, keys):
    names = tmc_names()
    with open(os.path.join(OUT, "chr_characters.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "id", "char_id", "code", "body_tmc", "body_name", "face_tmc", "face_name"])
        for row, (start, end) in enumerate(child_spans(buf, chrall)):
            words = struct.unpack_from("<%dI" % ((end - start) // 4), buf, start)
            found = {keys[v][0]: keys[v][1].rpartition("/")[2] for v in words if v in keys}
            body, face = found.get(39, ""), found.get(19, "")
            body_name = names.get(body, "")
            code = body_name[4:] if body_name.startswith("chr_") else ""
            w.writerow([row, "%08x" % words[0], words[0] & 0xFFFF, code, body, body_name, face, names.get(face, "")])


def main():
    buf = archive_dir.load_root("COMMON")
    keys = {}
    for root in ("COMMON", "HIGH"):
        data = buf if root == "COMMON" else archive_dir.load_root(root)
        if data is None:
            continue
        for r in archive_dir.records(data):
            keys[r["key"]] = (r["type"], r["path"])
    write_tmc_pairs(buf, keys)
    chr_data = find_chr_data(buf)
    kinds = motion_kinds()
    out_dir = os.path.join(OUT, "chr_data")
    os.makedirs(out_dir, exist_ok=True)

    def word(v):
        if v in keys:
            kind, path = keys[v]
            return "%d:%s" % (kind, path)
        return "%08x" % v

    sections = collections.Counter()
    motion_rows = []
    for section in children(buf, chr_data):
        name = block_name(buf, section)
        index = sections[name]
        sections[name] += 1
        label = name if index == 0 else "%s_%d" % (name, index)
        rows = []
        spans = child_spans(buf, section) if any(is_block(buf, c) for c in children(buf, section)) else [(section, None)]
        for char, (block, _end) in enumerate(spans):
            if not is_block(buf, block):
                continue
            for row, (start, end) in enumerate(child_spans(buf, block)):
                words = struct.unpack_from("<%dI" % ((end - start) // 4), buf, start)
                rows.append([label, char, row, "%08x" % words[0]] + [word(v) for v in words[1:]])
                if name == "mot":
                    banks = [keys[v][1].rpartition("/")[2] for v in words if v in keys]
                    motion_rows.append([char, row, "%08x" % words[0], " ".join(banks),
                                        " ".join(kinds.get(h, "?") for h in banks)])
        width = max((len(r) for r in rows), default=4)
        with open(os.path.join(out_dir, label + ".csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["section", "char", "row", "id"] + ["w%d" % i for i in range(1, width - 3)])
            w.writerows(rows)
        print(label, "rows", len(rows))
        if name == "chrall":
            write_characters(buf, section, keys)
    with open(os.path.join(OUT, "chr_motion_sets.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["char", "row", "id", "banks", "kinds"])
        w.writerows(motion_rows)
    print("motion sets", len(motion_rows))


if __name__ == "__main__":
    main()
