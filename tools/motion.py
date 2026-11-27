# -*- coding: utf-8 -*-
"""char_dat motion parser (KTGL piecewise-polynomial tracks).

A motion is a char_dat block whose entries are
  [0] track data: one u64 offset per clip (the first one also marks the end of
      the list), each pointing to a table of u64 offsets per (node, channel)
  [2] 0x20-byte meta
  [3] info: u32 at +8 = node count, name at +0x10 (the first node's name)
  [4] hierarchy (char_dat, one entry per node: parent, child count, children)
  [5] clip lookup: 1024 buckets of (u32 name hash, clip index)
Each node has 9 channels: translate xyz, rotate xyz (radians, applied x then
y then z), scale xyz. Character motions drive the 21 bones MOT00_Hips ..
MOT20_RightToe, which are nodes 0..20 of every body TMC.

Track keys (decoder at 0x140124EA0 in DOAX_VV.exe, key table 0x143BBF170):
  b0 = [hi:4][flag:1][dur_hi:3], b1 = [dur_lo:6][class:2]
  duration = frames until the next key; class 0 with duration 0 ends the track.
  Plain keys hold a 20-bit value (hi nibble, b2, b3) * 1e-4; flagged keys
  (hi selects the kind) hold a 32-bit value in b2..b5 * 1e-4. A flagged key
  whose (class, hi) is not a known kind reuses the previous key's kind.
"""
import os
import struct
import sys

import numpy as np

SCALE = 1e-4
CURVE_16 = 2.0 ** -15
TANGENT_16 = 2.0 ** -17

# (key size, segment kind, 32-bit values) for plain keys by class, flagged keys by (class, hi)
PLAIN = {0: (0, "end", False), 1: (4, "linear", False), 2: (6, "quad16", False), 3: (8, "hermite16", False)}
FLAGGED = {(1, 4): (6, "linear", True), (2, 6): (8, "quad16", True), (2, 7): (10, "quad32", True),
           (3, 9): (10, "hermite16", True), (3, 10): (12, "hermite24", True), (0, 11): (0, "end", True)}
WIDE_KINDS = set(FLAGGED) | {(2, 5), (3, 8)}


def s16(hi, lo):
    v = (hi << 8) | lo
    return v - 0x10000 if v & 0x8000 else v


def s24(a, b, c):
    v = (a << 16) | (b << 8) | c
    return v - 0x1000000 if v & 0x800000 else v


def s32(a, b, c, d):
    return struct.unpack(">i", bytes((a, b, c, d)))[0]


class Key:
    __slots__ = ("duration", "size", "kind", "wide", "is_wide", "raw")

    def __init__(self, raw, previous):
        b0, b1 = raw[0], raw[1]
        self.raw = raw
        self.duration = ((b0 & 7) << 6) | (b1 >> 2)
        cls, hi = b1 & 3, b0 >> 4
        self.is_wide = bool(b0 & 8) and (cls, hi) in WIDE_KINDS
        if self.duration == 0 and cls == 0:
            self.size, self.kind, self.wide = PLAIN[0] if hi != 11 else FLAGGED[(0, 11)]
        elif not b0 & 8:
            self.size, self.kind, self.wide = PLAIN[cls]
        elif (cls, hi) in FLAGGED:
            self.size, self.kind, self.wide = FLAGGED[(cls, hi)]
        elif previous is not None:
            self.size, self.kind, self.wide = previous.size, previous.kind, previous.wide
        else:
            raise ValueError("unknown first key %02x %02x" % (b0, b1))

    def value(self, wide):
        r = self.raw
        if wide:
            return s32(r[2], r[3], r[4], r[5]) * SCALE
        hi = r[0] >> 4
        v = (hi << 16) | (r[2] << 8) | r[3]
        return (v - 0x100000 if hi & 8 else v) * SCALE


def keys(track):
    pos = 0
    if len(track) >= 2 and track[0] == 0 and track[1] == 2:
        pos += 16
    while pos + 2 <= len(track) and track[pos] == 0 and track[pos + 1] == 3:
        pos += 8
    out = []
    while pos + 2 <= len(track):
        key = Key(track[pos:pos + 12].ljust(12, b"\0"), out[-1] if out else None)
        out.append(key)
        if key.kind == "end" or key.size == 0:
            break
        pos += key.size
    return out


def segments(track):
    """List of (start_frame, duration, c0, c1, c2, c3); the last one is constant."""
    ks = keys(track)
    out, frame = [], 0
    for key, nxt in zip(ks, ks[1:]):
        d = float(key.duration)
        v0 = key.value(key.wide)
        v1 = nxt.value(key.wide if key.is_wide == nxt.is_wide else not key.wide)
        dv = v1 - v0
        r = key.raw
        c1 = c2 = c3 = 0.0
        if d == 0:
            pass
        elif key.kind == "linear":
            c1 = dv / d
        elif key.kind in ("quad16", "quad32"):
            if key.kind == "quad32":
                k = s32(r[8], r[9], r[6], r[7]) * SCALE
            elif key.wide:
                k = s16(r[6], r[7]) * CURVE_16
            else:
                k = s16(r[4], r[5]) * CURVE_16
            c2 = -k
            c1 = dv / d - c2 * d
        else:
            if key.kind == "hermite24":
                m0, m1 = s24(r[8], r[6], r[7]) * SCALE, s24(r[9], r[10], r[11]) * SCALE
            elif key.wide:
                m0, m1 = s16(r[6], r[7]) * TANGENT_16, s16(r[8], r[9]) * TANGENT_16
            else:
                m0, m1 = s16(r[4], r[5]) * TANGENT_16, s16(r[6], r[7]) * TANGENT_16
            c1 = m0
            c2 = 3 * dv / (d * d) - (2 * m0 + m1) / d
            c3 = (m0 + m1) / (d * d) - 2 * dv / (d * d * d)
        out.append((frame, key.duration, v0, c1, c2, c3))
        frame += key.duration
    out.append((frame, 0, ks[-1].value(ks[-1].wide), 0.0, 0.0, 0.0))
    return out


def is_delta(track):
    return len(track) >= 2 and track[0] == 0 and track[1] == 7


def s8(b):
    return b - 0x100 if b & 0x80 else b


def delta_values(track):
    """Per-frame values of a delta-coded track (header 00 07, reader at 0x140124B00).

    Tokens are [count lo, count hi, code, ...]; any other code byte makes a
    24-bit absolute value. 0x7F/0x7E: count frames of 1/2-byte deltas, 0x7D/0x7C:
    one 1/2-byte delta repeated count times, 0x7B: 32-bit absolute value, 0x80 and
    (after the first token) 0x7A: last value. Values are fixed point / 16384.
    """
    t = track
    pos, value, out = 2, 0, []
    while pos + 3 <= len(t):
        b0, b1, code = t[pos], t[pos + 1], t[pos + 2]
        count = b0 | b1 << 8
        if code == 0x80:
            out.append(s8(t[pos + 3]) << 16 | b1 << 8 | b0)
            break
        if code == 0x7A and out:
            out.append(s8(t[pos + 4]) << 24 | t[pos + 3] << 16 | b1 << 8 | b0)
            break
        if not out or not 0x7B <= code <= 0x7F:
            value = s8(code) << 16 | b1 << 8 | b0
            out.append(value)
            pos += 3
        elif code == 0x7B:
            value = s8(t[pos + 4]) << 24 | t[pos + 3] << 16 | b1 << 8 | b0
            out.append(value)
            pos += 5
        elif code == 0x7F:
            for i in range(count):
                value += s8(t[pos + 3 + i])
                out.append(value)
            pos += 3 + count
        elif code == 0x7E:
            for i in range(count):
                value += s16(t[pos + 4 + 2 * i], t[pos + 3 + 2 * i])
                out.append(value)
            pos += 3 + 2 * count
        elif code == 0x7D:
            for _ in range(count):
                value += s8(t[pos + 3])
                out.append(value)
            pos += 4
        else:
            # 0x7C: the game reads the first delta at +3 and the repeats at +4
            value += s16(t[pos + 4], t[pos + 3])
            out.append(value)
            for _ in range(count - 1):
                value += s16(t[pos + 5], t[pos + 4])
                out.append(value)
            pos += 5
    return np.array(out, dtype=np.float64) / 16384.0


def sample(track, frames):
    frames = np.asarray(frames, dtype=np.float64)
    if is_delta(track):
        values = delta_values(track)
        return np.interp(frames, np.arange(len(values)), values)
    segs = segments(track)
    starts = np.array([s[0] for s in segs])
    coef = np.array([s[2:] for s in segs], dtype=np.float64)
    idx = np.clip(np.searchsorted(starts, frames, side="right") - 1, 0, len(segs) - 1)
    t = frames - starts[idx]
    c = coef[idx]
    return ((c[:, 3] * t + c[:, 2]) * t + c[:, 1]) * t + c[:, 0]


def length(track):
    if is_delta(track):
        return len(delta_values(track)) - 1
    return segments(track)[-1][0]


def u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def entries(buf, base):
    return [u32(buf, base + 0x30 + 4 * i) for i in range(u32(buf, base + 0x14))]


class Motion:
    def __init__(self, buf, base):
        segs = entries(buf, base)
        self.base = base
        info = base + segs[3]
        self.node_count = u32(buf, info + 8)
        self.name = buf[info + 0x10:info + 0x50].split(b"\0")[0].decode("ascii", "replace")
        self.meta = buf[base + segs[2]:base + segs[2] + 0x20]
        hie = base + segs[4]
        self.parents = []
        for off in entries(buf, hie)[:self.node_count]:
            self.parents.append(struct.unpack_from("<i", buf, hie + off)[0])
        data = base + segs[0]
        end = (segs[1] or segs[2]) - segs[0]
        first = u32(buf, data)
        tables = [t for t in struct.unpack_from("<%dQ" % (first // 8), buf, data) if t]
        offsets = [struct.unpack_from("<%dQ" % (self.node_count * 9), buf, data + t) for t in tables]
        bounds = np.array(sorted(set(tables).union(*offsets)) + [end])
        self.clips = []
        for clip in offsets:
            stops = bounds[np.searchsorted(bounds, clip, side="right")]
            self.clips.append([bytes(buf[data + a:data + b]) for a, b in zip(clip, stops)])
        self.tracks = self.clips[0]
        self.frames = max(length(t) for t in self.tracks)

    def clip_frames(self, clip):
        return max(length(t) for t in self.clips[clip])

    def channels(self, frames, clip=0):
        """Array (frames, nodes, 9)."""
        out = np.zeros((len(frames), self.node_count, 9), dtype=np.float64)
        for i, track in enumerate(self.clips[clip]):
            out[:, i // 9, i % 9] = sample(track, frames)
        return out


def quat_mul(a, b):
    ax, ay, az, aw = np.moveaxis(a, -1, 0)
    bx, by, bz, bw = np.moveaxis(b, -1, 0)
    return np.stack([aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw,
                     aw * bw - ax * bx - ay * by - az * bz], -1)


def euler_to_quat(euler):
    """(..., 3) radians, rotate about x then y then z -> (..., 4) xyzw quaternions."""
    half = np.asarray(euler, dtype=np.float64) / 2
    c, s = np.cos(half), np.sin(half)
    zero = np.zeros_like(c[..., 0])
    qx = np.stack([s[..., 0], zero, zero, c[..., 0]], -1)
    qy = np.stack([zero, s[..., 1], zero, c[..., 1]], -1)
    qz = np.stack([zero, zero, s[..., 2], c[..., 2]], -1)
    return hemisphere(quat_mul(qz, quat_mul(qy, qx)))


def hemisphere(q):
    """Flip quaternions along axis 0 (frames) so consecutive ones stay in the same hemisphere."""
    if q.ndim >= 2 and len(q) > 1:
        flips = np.cumsum(np.sum(q[1:] * q[:-1], -1) < 0, axis=0) % 2
        q[1:] *= np.where(flips, -1.0, 1.0)[..., None]
    return q


def quat_rotate(q, v):
    u, w = q[..., :3], q[..., 3:]
    t = 2 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


def motions(buf, base=0):
    """Yield every motion block below a char_dat block (depth-first)."""
    if buf[base:base + 8] != b"char_dat":
        return
    segs = entries(buf, base)
    nested = [s for s in segs if s and buf[base + s:base + s + 8] == b"char_dat"]
    if len(segs) >= 5 and segs[3] and segs[4] and buf[base + segs[4]:base + segs[4] + 8] == b"char_dat" \
            and len(nested) == 1:
        yield Motion(buf, base)
        return
    for s in nested:
        yield from motions(buf, base + s)


def main():
    """python tools\\motion.py <char_dat hash prefix> ...  lists motions and clip lengths."""
    import csv
    import export_gltf
    wanted = sys.argv[1:]
    rows = [r for r in csv.DictReader(open(export_gltf.INDEX, encoding="utf-8"))
            if r["magic"] == "char_dat" and any(r["hash"].startswith(w) for w in wanted)]
    for row in rows:
        buf = export_gltf.read_inflated(row)
        print(row["folder"], row["hash"], len(buf))
        for number, motion in enumerate(motions(buf)):
            lengths = [motion.clip_frames(c) for c in range(len(motion.clips))]
            print("  motion %d %s nodes=%d clips=%d frames=%s" % (
                number, motion.name, motion.node_count, len(lengths), lengths[:16]))


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))
    main()
