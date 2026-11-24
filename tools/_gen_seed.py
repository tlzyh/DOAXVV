# -*- coding: utf-8 -*-
"""Rebuild the runtime XOR seed and try it on one COMMON file."""
import os
import re
import struct

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

EXE = r"E:\Games\DMM\DOAX-VenusVacation\DOAX_VV.exe"
IMAGE = 0x140000000
BEGIN = 0x142DE6250
END = 0x142DE6B4E
N = 624
M = 397
MATRIX = 0x9908B0DF


def f32_mul(a_bits, b_bits):
    """IEEE-754 float32 multiply via round-trip through Python is not enough.
    Use the mantissa math of struct only for conversion; multiply in numpy if present.
    """
    raise NotImplementedError


def load_table(data):
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    blob = data[0x400 + (BEGIN - IMAGE - 0x1000):0x400 + (END - IMAGE - 0x1000)]
    xmm = {0: None, 1: None}
    table = {}
    floats = {}
    for insn in md.disasm(blob, BEGIN):
        raw = bytes(insn.bytes)
        text = insn.op_str
        if insn.mnemonic == "movdqa" and text.startswith("xmm") and text[3].isdigit():
            reg = int(text[3])
            disp = struct.unpack_from("<i", raw, raw.index(0x6F) + 2)[0]
            src = insn.address + insn.size + disp
            off = 0x324FE00 + (src - IMAGE - 0x3251000)
            xmm[reg] = data[off:off + 16]
        elif insn.mnemonic == "movdqa" and "[rbp" in text:
            reg = int(text.rsplit("xmm", 1)[1])
            match = re.search(r"0x([0-9a-f]+)", text)
            table[int(match.group(1), 16)] = xmm[reg]
        elif insn.mnemonic == "movss" and text.startswith("xmm"):
            reg = int(text[3])
            disp = struct.unpack_from("<i", raw, len(raw) - 4)[0]
            src = insn.address + insn.size + disp
            off = 0x324FE00 + (src - IMAGE - 0x3251000)
            floats[reg] = struct.unpack_from("<f", data, off)[0]
    base = 0x900
    raw = bytearray()
    off = base
    while off < 0xE60:
        raw += table[off]
        off += 16
    dwords = list(struct.unpack("<" + "I" * (len(raw) // 4), raw))
    return dwords, floats


def mt_seed(seed):
    mt = [0] * N
    mt[0] = seed & 0xFFFFFFFF
    for i in range(1, N):
        prev = mt[i - 1]
        mt[i] = (0x6C078965 * (prev ^ (prev >> 30)) + i) & 0xFFFFFFFF
    # the init function twists once
    twist(mt)
    return mt, 0, N  # state, pos, left


def twist(mt):
    for i in range(N - M):
        mt[i] = _mix(mt[i], mt[i + 1], mt[i + M])
    for i in range(N - M, N - 1):
        mt[i] = _mix(mt[i], mt[i + 1], mt[i + (M - N)])
    mt[N - 1] = _mix(mt[N - 1], mt[0], mt[M - 1])


def _mix(cur, nxt, mix):
    y = cur ^ ((cur ^ nxt) & 0x7FFFFFFE)
    y = (y >> 1) & 0x7FFFFFFF
    if nxt & 1:
        y ^= MATRIX
    return (y ^ mix) & 0xFFFFFFFF


def temper(y):
    y ^= (y >> 11)
    y ^= (y << 7) & 0xFF3A58AD
    y ^= (y << 15) & 0xFFFFDF8C
    y ^= (y >> 18)
    return y & 0xFFFFFFFF


class MT:
    def __init__(self, seed):
        self.mt, self.pos, self.left = mt_seed(seed)

    def _raw(self):
        # The binary decrements the counter first and twists when it hits 0,
        # so the 624th draw twists before reading and never emits mt[623].
        self.left -= 1
        if self.left == 0:
            twist(self.mt)
            self.pos = 0
            self.left = N
        y = self.mt[self.pos]
        self.pos += 1
        return temper(y)


def f32_from_u32(value):
    import numpy as np
    return np.float32(np.int64(value))


def build_variants(dwords, floats):
    import numpy as np
    scale = np.float32(floats[8])
    limit = np.float32(floats[6])
    byte_scale = np.float32(floats[7])
    zero = np.float32(0.0)

    def draw(rng):
        while True:
            sample = f32_from_u32(rng._raw()) * scale
            if sample >= zero and sample < limit:
                return int(sample * byte_scale) & 0xFF

    rng = MT(0x6F)
    mixed = dwords[:]
    for i in range(0x158):
        mixed[i] ^= draw(rng)
    rng = MT(0x6F)
    both = bytes(((mixed[i] & 0xFF) - draw(rng)) & 0xFF for i in range(0x158))
    rng = MT(0x6F)
    only_sub = bytes(((dwords[i] & 0xFF) - draw(rng)) & 0xFF for i in range(0x158))
    raw = bytes(d & 0xFF for d in dwords)
    return {"both": both, "sub": only_sub, "raw": raw}


def build_seed(dwords, floats):
    import numpy as np
    scale = np.float32(floats[8])
    limit = np.float32(floats[6])
    byte_scale = np.float32(floats[7])
    zero = np.float32(0.0)
    table = dwords[:]
    rng = MT(0x6F)
    for i in range(0x158):
        while True:
            sample = f32_from_u32(rng._raw()) * scale
            if sample >= zero and sample < limit:
                break
        drawn = int(sample * byte_scale)
        table[i] ^= drawn & 0xFFFFFFFF
    rng = MT(0x6F)
    out = bytearray(0x158)
    for i in range(0x158):
        while True:
            sample = f32_from_u32(rng._raw()) * scale
            if sample >= zero and sample < limit:
                break
        drawn = int(sample * byte_scale)
        out[i] = (table[i] - drawn) & 0xFF
    return bytes(out)


def file_key(index):
    dword = (index * 0x77) // 11
    raw = dword.to_bytes(4, "big")
    return bytes(b for b in raw if b)


def decrypt(data, seed, key):
    out = bytearray(data)
    size = len(data)
    stride = 1
    rounded = ((size + stride - 1) // stride) * stride
    pos = rounded - size
    index = rounded
    while pos < size:
        val = out[pos]
        mix = seed[index % len(seed)]
        if key:
            mix ^= key[index % len(key)]
        if val and val != mix:
            out[pos] = val ^ mix
        pos += stride
        index += stride
    return bytes(out)


def main():
    data = open(EXE, "rb").read()
    dwords, floats = load_table(data)
    print("dwords", len(dwords), "floats", {k: floats[k] for k in floats})
    variants = build_variants(dwords, floats)
    for label, seed in variants.items():
        print(label, seed[:16].hex())
    common = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\COMMON"
    blob = None
    for entry in os.listdir(common):
        if entry.startswith("0030753cd83f82d7"):
            blob = open(os.path.join(common, entry), "rb").read(128)
            break
    magics = (b"GT1G", b"_N1G", b"_M1G", b"_A2G", b"_A1G", b"_L1G", b"OC1G")
    keys = [b"", file_key(1), file_key(2), file_key(3)]
    for label, seed in variants.items():
        for key in keys:
            for phase in range(len(seed)):
                out = bytearray(blob)
                for pos, val in enumerate(blob):
                    index = phase + pos
                    mix = seed[index % len(seed)]
                    if key:
                        mix ^= key[index % len(key)]
                    if val and val != mix:
                        out[pos] = val ^ mix
                if bytes(out[:4]) in magics or bytes(out[4:8]) in magics:
                    print("HIT", label, key.hex(), phase, bytes(out[:12]))


if __name__ == "__main__":
    main()
