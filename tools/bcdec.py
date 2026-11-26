# -*- coding: utf-8 -*-
"""Decode the top mip of a DDS (BC7 or uncompressed masks) to RGBA and write PNG, numpy only.

The BC7 partition and anchor tables below were measured against a reference
decoder by encoding synthetic blocks; they match the D3D11 specification.
"""
import struct
import zlib

import numpy as np

P2 = ("0011001100110011 0001000100010001 0111011101110111 0001001100110111 0000000100010011 0011011101111111 "
      "0001001101111111 0000000100110111 0000000000010011 0011011111111111 0000000101111111 0000000000010111 "
      "0001011111111111 0000000011111111 0000111111111111 0000000000001111 0000100011101111 0111000100000000 "
      "0000000010001110 0111001100010000 0011000100000000 0000100011001110 0000000010001100 0111001100110001 "
      "0011000100010000 0000100010001100 0110011001100110 0011011001101100 0001011111101000 0000111111110000 "
      "0111000110001110 0011100110011100 0101010101010101 0000111100001111 0101101001011010 0011001111001100 "
      "0011110000111100 0101010110101010 0110100101101001 0101101010100101 0111001111001110 0001001111001000 "
      "0011001001001100 0011101111011100 0110100110010110 0011110011000011 0110011010011001 0000011001100000 "
      "0100111001000000 0010011100100000 0000001001110010 0000010011100100 0110110010010011 0011011011001001 "
      "0110001110011100 0011100111000110 0110110011001001 0110001100111001 0111111010000001 0001100011100111 "
      "0000111100110011 0011001111110000 0010001011101110 0100010001110111").split()
P3 = ("0011001102212222 0001001122112221 0000200122112211 0222002200110111 0000000011221122 0011001100220022 "
      "0022002211111111 0011001122112211 0000000011112222 0000111111112222 0000111122222222 0012001200120012 "
      "0112011201120112 0122012201220122 0011011211221222 0011200122002220 0001001101121122 0111001120012200 "
      "0000112211221122 0022002200221111 0111011102220222 0001000122212221 0000001101220122 0000110022102210 "
      "0122012200110000 0012001211222222 0110122112210110 0000011012211221 0022110211020022 0110011020022222 "
      "0011012201220011 0000200022112221 0000000211221222 0222002200120011 0011001200220222 0120012001200120 "
      "0000111122220000 0120120120120120 0120201212010120 0011220011220011 0011112222000011 0101010122222222 "
      "0000000021212121 0022112200221122 0022001100220011 0220122102201221 0101222222220101 0000212121212121 "
      "0101010101012222 0222011102220111 0002111200021112 0000211221122112 0222011101110222 0002111211120002 "
      "0110011001102222 0000000021122112 0110011022222222 0022001100110022 0022112211220022 0000000000002112 "
      "0002000100020001 0222122202221222 0101222222222222 0111201122012220").split()
A2 = [15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 8, 2, 2, 8, 8, 15, 2, 8, 2, 2, 8, 8, 2, 2,
      15, 15, 6, 8, 2, 8, 15, 15, 2, 8, 2, 2, 2, 15, 15, 6, 6, 2, 6, 8, 15, 15, 2, 2, 15, 15, 15, 15, 15, 2, 2, 15]
A3A = [3, 3, 15, 15, 8, 3, 15, 15, 8, 8, 6, 6, 6, 5, 3, 3, 3, 3, 8, 15, 3, 3, 6, 10, 5, 8, 8, 6, 8, 5, 15, 15,
       8, 15, 3, 5, 6, 10, 8, 15, 15, 3, 15, 5, 15, 15, 15, 15, 3, 15, 5, 5, 5, 8, 5, 10, 5, 10, 8, 13, 15, 12, 3, 3]
A3B = [15, 8, 8, 3, 15, 15, 3, 8, 15, 15, 15, 15, 15, 15, 15, 8, 15, 8, 15, 3, 15, 8, 15, 8, 3, 15, 6, 10, 15, 15, 10, 8,
       15, 3, 15, 10, 10, 8, 9, 10, 6, 15, 8, 15, 3, 6, 6, 8, 15, 3, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 3, 15, 15, 8]

SUBSETS = {1: np.zeros((64, 16), np.int64),
           2: np.array([[int(c) for c in row] for row in P2]),
           3: np.array([[int(c) for c in row] for row in P3])}
ANCHORS = {1: np.zeros((64, 3), np.int64),
           2: np.array([[0, a, 0] for a in A2]),
           3: np.array([[0, a, b] for a, b in zip(A3A, A3B)])}
WEIGHTS = {2: np.array([0, 21, 43, 64]), 3: np.array([0, 9, 18, 27, 37, 46, 55, 64]),
           4: np.array([0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64])}
# subsets, partition bits, rotation bits, index-select bits, color bits, alpha bits,
# per-endpoint p-bit, shared p-bit, index bits, secondary index bits
MODES = {
    0: (3, 4, 0, 0, 4, 0, 1, 0, 3, 0), 1: (2, 6, 0, 0, 6, 0, 0, 1, 3, 0),
    2: (3, 6, 0, 0, 5, 0, 0, 0, 2, 0), 3: (2, 6, 0, 0, 7, 0, 1, 0, 2, 0),
    4: (1, 0, 2, 1, 5, 6, 0, 0, 2, 3), 5: (1, 0, 2, 0, 7, 8, 0, 0, 2, 2),
    6: (1, 0, 0, 0, 7, 7, 1, 0, 4, 0), 7: (2, 6, 0, 0, 5, 5, 1, 0, 2, 0),
}


def _take(bits, start, count):
    """Read `count` bits at per-row (or scalar) `start` from a (n, 128) bit array."""
    rows = np.arange(bits.shape[0])
    start = np.broadcast_to(np.asarray(start), (bits.shape[0],) if np.ndim(start) <= 1 else start.shape)
    value = np.zeros(start.shape, np.int64)
    for k in range(count):
        if start.ndim == 1:
            value |= bits[rows, start + k].astype(np.int64) << k
        else:
            value |= bits[rows[:, None], start + k].astype(np.int64) << k
    return value


def _expand(value, precision):
    value = value << (8 - precision)
    return value | (value >> precision)


def _decode_mode(bits, mode):
    ns, pb, rb, isb, cb, ab, epb, spb, ib, ib2 = MODES[mode]
    n = bits.shape[0]
    pos = mode + 1
    partition = _take(bits, pos, pb) if pb else np.zeros(n, np.int64)
    pos += pb
    rotation = _take(bits, pos, rb) if rb else np.zeros(n, np.int64)
    pos += rb
    select = _take(bits, pos, isb) if isb else np.zeros(n, np.int64)
    pos += isb
    ends = 2 * ns
    color = np.zeros((n, ends, 4), np.int64)
    for ch in range(3):
        for e in range(ends):
            color[:, e, ch] = _take(bits, pos, cb)
            pos += cb
    if ab:
        for e in range(ends):
            color[:, e, 3] = _take(bits, pos, ab)
            pos += ab
    cprec, aprec = cb, ab
    if epb or spb:
        pbit = np.zeros((n, ends), np.int64)
        if epb:
            for e in range(ends):
                pbit[:, e] = _take(bits, pos, 1)
                pos += 1
        else:
            for s in range(ns):
                pbit[:, 2 * s] = pbit[:, 2 * s + 1] = _take(bits, pos, 1)
                pos += 1
        color[:, :, :3] = (color[:, :, :3] << 1) | pbit[:, :, None]
        cprec += 1
        if ab:
            color[:, :, 3] = (color[:, :, 3] << 1) | pbit
            aprec += 1
    color[:, :, :3] = _expand(color[:, :, :3], cprec)
    color[:, :, 3] = _expand(color[:, :, 3], aprec) if ab else 255

    subset = SUBSETS[ns][partition]
    anchors = ANCHORS[ns][partition]
    is_anchor = np.zeros((n, 16), bool)
    for s in range(ns):
        is_anchor[np.arange(n), anchors[:, s]] = True
    widths = np.where(is_anchor, ib - 1, ib)
    starts = pos + np.cumsum(widths, axis=1) - widths
    primary = np.zeros((n, 16), np.int64)
    for k in range(ib):
        live = k < widths
        primary |= np.where(live, _take(bits, np.where(live, starts + k, 0), 1), 0) << k
    pos += 16 * ib - ns
    secondary = None
    if ib2:
        widths2 = np.full((n, 16), ib2)
        widths2[:, 0] = ib2 - 1
        starts2 = pos + np.cumsum(widths2, axis=1) - widths2
        secondary = np.zeros((n, 16), np.int64)
        for k in range(ib2):
            live = k < widths2
            secondary |= np.where(live, _take(bits, np.where(live, starts2 + k, 0), 1), 0) << k

    rows = np.arange(n)[:, None]
    e0 = color[rows, subset * 2]
    e1 = color[rows, subset * 2 + 1]
    if secondary is None:
        weight = WEIGHTS[ib][primary]
        out = ((64 - weight)[..., None] * e0 + weight[..., None] * e1 + 32) >> 6
    else:
        swap = (select == 1)[:, None]
        cidx = np.where(swap, secondary, primary)
        aidx = np.where(swap, primary, secondary)
        cw = np.where(swap, WEIGHTS[ib2][np.minimum(cidx, (1 << ib2) - 1)], WEIGHTS[ib][np.minimum(cidx, (1 << ib) - 1)])
        aw = np.where(swap, WEIGHTS[ib][np.minimum(aidx, (1 << ib) - 1)], WEIGHTS[ib2][np.minimum(aidx, (1 << ib2) - 1)])
        out = np.empty((n, 16, 4), np.int64)
        out[..., :3] = ((64 - cw)[..., None] * e0[..., :3] + cw[..., None] * e1[..., :3] + 32) >> 6
        out[..., 3] = ((64 - aw) * e0[..., 3] + aw * e1[..., 3] + 32) >> 6
    for value, channel in ((1, 0), (2, 1), (3, 2)):
        hit = rotation == value
        if hit.any():
            alpha = out[hit, :, 3].copy()
            out[hit, :, 3] = out[hit, :, channel]
            out[hit, :, channel] = alpha
    return out


def decode_bc7(data, width, height):
    bw, bh = (width + 3) // 4, (height + 3) // 4
    blocks = np.frombuffer(data, np.uint8, bw * bh * 16).reshape(-1, 16)
    bits = np.unpackbits(blocks, axis=1, bitorder="little")
    first = bits[:, :8]
    mode = np.where(first.any(1), first.argmax(1), 8)
    pixels = np.zeros((blocks.shape[0], 16, 4), np.int64)
    for m in range(8):
        sel = mode == m
        if sel.any():
            pixels[sel] = _decode_mode(bits[sel], m)
    image = pixels.reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)
    return image[:height, :width].astype(np.uint8)


def _mask_channel(values, mask):
    if not mask:
        return None
    shift = (mask & -mask).bit_length() - 1
    top = mask >> shift
    channel = (values >> shift) & top
    return (channel * 255 // top).astype(np.uint8)


def decode_dds(data):
    """Return (rgba uint8 array, dxgi format or fourcc) for the top mip."""
    if data[:4] != b"DDS ":
        raise ValueError("not a DDS")
    height, width = struct.unpack_from("<II", data, 12)
    pf_flags, fourcc, bitcount = struct.unpack_from("<I4sI", data, 80)
    masks = struct.unpack_from("<4I", data, 92)
    offset = 128
    if fourcc == b"DX10":
        dxgi = struct.unpack_from("<I", data, 128)[0]
        offset = 148
        if dxgi in (98, 99):
            return decode_bc7(data[offset:], width, height), dxgi
        if dxgi in (28, 29):
            return np.frombuffer(data, np.uint8, width * height * 4, offset).reshape(height, width, 4).copy(), dxgi
        if dxgi in (87, 91):
            return np.frombuffer(data, np.uint8, width * height * 4, offset).reshape(height, width, 4)[..., [2, 1, 0, 3]].copy(), dxgi
        raise ValueError("unsupported DXGI format %d" % dxgi)
    if pf_flags & 0x4:
        raise ValueError("unsupported FourCC %r" % fourcc)
    step = bitcount // 8
    raw = np.frombuffer(data, np.uint8, width * height * step, offset).reshape(-1, step)
    values = np.zeros(raw.shape[0], np.uint64)
    for k in range(step):
        values |= raw[:, k].astype(np.uint64) << np.uint64(8 * k)
    values = values.astype(np.int64)
    rgba = np.full((width * height, 4), 255, np.uint8)
    for ch, mask in enumerate(masks):
        channel = _mask_channel(values, mask)
        if channel is not None:
            rgba[:, ch] = channel
    if pf_flags & 0x20000 and masks[0] and not masks[1]:
        rgba[:, 1] = rgba[:, 2] = rgba[:, 0]
    return rgba.reshape(height, width, 4), "masks"


def write_png(path, rgba, level=6):
    height, width = rgba.shape[:2]
    rows = np.concatenate([np.zeros((height, 1), np.uint8), rgba.reshape(height, width * 4)], axis=1)

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        handle.write(chunk(b"IDAT", zlib.compress(rows.tobytes(), level)))
        handle.write(chunk(b"IEND", b""))
