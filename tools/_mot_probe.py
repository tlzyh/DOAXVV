# -*- coding: utf-8 -*-
"""Scratch probe of char_dat motion tracks (reads out\\_mot_sample.bin)."""
import collections
import struct
import sys

d = open(sys.argv[1] if len(sys.argv) > 1 else r"out\_mot_sample.bin", "rb").read()
u = lambda o: struct.unpack_from("<I", d, o)[0]


def children(base):
    return [base + u(base + 0x30 + 4 * i) for i in range(u(base + 0x14)) if u(base + 0x30 + 4 * i)]


def motion(c):
    segs = [u(c + 0x30 + 4 * i) for i in range(u(c + 0x14))]
    size = u(c + 0x10)
    tracks_seg = c + segs[0]
    info = c + segs[3]
    nodes = u(info + 8)
    name = d[info + 0x10:info + 0x50].split(b"\0")[0].decode()
    meta = d[c + segs[2]:c + segs[2] + 0x20]
    table_off = u(tracks_seg)
    table = [u(tracks_seg + table_off + 8 * i) for i in range(nodes * 9)]
    ends = sorted(set(table)) + [segs[1] - segs[0] if segs[1] else segs[2] - segs[0]]
    tracks = []
    for off in table:
        end = min(e for e in ends if e > off)
        tracks.append(d[tracks_seg + off:tracks_seg + end])
    return name, nodes, meta, tracks


if __name__ == "__main__":
    stats = collections.Counter()
    for c in children(0):
        name, nodes, meta, tracks = motion(c)
        print(name, "nodes", nodes, "meta", meta.hex(" "))
        for t in tracks:
            stats[(t[0], t[1])] += 1
    for (kind, b1), n in sorted(stats.items()):
        print("type %d b1 %02x (%s) x%d" % (kind, b1, format(b1, "08b"), n))
