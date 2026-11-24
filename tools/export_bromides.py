# -*- coding: utf-8 -*-
"""Export every BROMIDE archive to a PNG."""
import argparse
import csv
import os
import struct
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from decrypt import SEED, iter_pages

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
LIST = r"D:\Projects\YangHui\DOAXVV\tools\_bromide_list.csv"
OUT_DIR = r"D:\Projects\YangHui\DOAXVV\export\bromide"
KNOWN_PNG = r"D:\Projects\YangHui\DOAXVV\export\BROMIDE_OWN_ZA_91_A_LUN.png"
SEED_U8 = np.frombuffer(SEED, dtype=np.uint8)
MARKER = np.array([0xFF, 0xFF, 0x00, 0x00], dtype=np.uint8)


def decrypt_np(data, key):
    src = np.frombuffer(data, dtype=np.uint8)
    idx = np.arange(src.shape[0])
    key_u8 = np.frombuffer(bytes(key), dtype=np.uint8)
    mixed = np.bitwise_xor(SEED_U8[idx % SEED_U8.shape[0]], key_u8[idx % key_u8.shape[0]])
    out = np.bitwise_xor(src, mixed)
    np.copyto(out, src, where=(src == 0) | (src == mixed))
    return out.tobytes()


def image_info(page):
    end = page.find(b"\x00", 0x8C)
    pos = end + 1
    kind, wh = struct.unpack_from("<II", page, pos)
    width = wh & 0xFFFF
    height = wh >> 16
    return kind, width, height


def rgb565(values):
    red = ((values >> 11) & 31) * 255 // 31
    green = ((values >> 5) & 63) * 255 // 63
    blue = (values & 31) * 255 // 31
    return np.stack([red, green, blue], axis=1).astype(np.uint32)


def decode_dxt1(blocks, width, height):
    block_w = width // 4
    block_h = height // 4
    raw = blocks.astype(np.uint32)
    c0 = raw[:, 0] | (raw[:, 1] << 8)
    c1 = raw[:, 2] | (raw[:, 3] << 8)
    bits = raw[:, 4] | (raw[:, 5] << 8) | (raw[:, 6] << 16) | (raw[:, 7] << 24)
    col0 = rgb565(c0)
    col1 = rgb565(c1)
    four = c0 > c1
    col2 = np.where(four[:, None], (2 * col0 + col1) // 3, (col0 + col1) // 2)
    col3 = np.where(four[:, None], (col0 + 2 * col1) // 3, 0)
    colors = np.stack([col0, col1, col2, col3], axis=1)
    shifts = np.arange(16, dtype=np.uint32) * 2
    index = (bits[:, None] >> shifts) & 3
    picked = colors[np.arange(colors.shape[0])[:, None], index]
    count = min(picked.shape[0], block_w * block_h)
    tiled = np.zeros((block_h, block_w, 4, 4, 3), dtype=np.uint8)
    flat = tiled.reshape(block_h * block_w, 4, 4, 3)
    flat[:count] = picked[:count].reshape(count, 4, 4, 3).astype(np.uint8)
    return tiled.transpose(0, 2, 1, 3, 4).reshape(block_h * 4, block_w * 4, 3), count


def dxt_blocks(body):
    """Each record is 16 bytes: eight DXT1 bytes, a ffff0000 marker, and four pad bytes."""
    raw = np.frombuffer(body, dtype=np.uint8)
    best = None
    chosen = None
    for shift in range(16):
        span = raw[shift:]
        count = len(span) // 16
        if count < 16:
            continue
        view = span[:count * 16].reshape(count, 16)
        for at in range(13):
            ratio = float(np.all(view[:, at:at + 4] == MARKER, axis=1).mean())
            if ratio < 0.99:
                continue
            dxt_index = np.arange(at - 8, at) % 16
            used = np.zeros(16, dtype=bool)
            used[dxt_index] = True
            used[at:at + 4] = True
            pad_zero = float((view[:, np.flatnonzero(~used)] == 0).mean())
            score = (ratio, pad_zero)
            if best is None or score > best:
                best = score
                chosen = (shift, dxt_index, view)
    if chosen is None:
        raise ValueError("no aligned blocks")
    _shift, dxt_index, view = chosen
    return view[:, dxt_index]


def decode_file(path, key):
    pages = [page for _pos, page in iter_pages(decrypt_np(open(path, "rb").read(), key))]
    if len(pages) < 2 or not pages[0].startswith(b"TLSK"):
        raise ValueError("no image pages")
    kind, width, height = image_info(pages[0])
    if kind != 3 or width == 0 or height == 0 or width % 4 or height % 4:
        raise ValueError(f"header {kind} {width}x{height}")
    blocks = dxt_blocks(b"".join(pages[1:]))
    image, used = decode_dxt1(blocks, width, height)
    return image, width, height, used


def export_one(job):
    folder, name, digest, key, dest = job
    path = os.path.join(ROOT, folder, digest)
    try:
        image, width, height, used = decode_file(path, bytes.fromhex(key))
        Image.fromarray(image, "RGB").save(dest, compress_level=1)
        return name, width, height, used, ""
    except Exception as exc:
        return name, 0, 0, 0, str(exc)


def load_jobs(limit):
    rows = list(csv.DictReader(open(LIST, encoding="utf-8")))
    rows.sort(key=lambda row: (row["name"], row["folder"], row["hash"]))
    if limit:
        rows = rows[:limit]
    seen = set()
    jobs = []
    for row in rows:
        base = row["name"]
        filename = base + ".png"
        if filename in seen:
            filename = f"{base}__{row['hash'][:8]}.png"
        seen.add(filename)
        jobs.append((row["folder"], row["name"], row["hash"], row["key"], os.path.join(OUT_DIR, filename)))
    return jobs


def check_known():
    jobs = load_jobs(0)
    known = next(job for job in jobs if job[2].startswith("005064dc5768a5f0"))
    image, width, height, used = decode_file(os.path.join(ROOT, known[0], known[2]), bytes.fromhex(known[3]))
    old = np.array(Image.open(KNOWN_PNG).convert("RGB"))
    same = np.array_equal(image[:old.shape[0], :old.shape[1]], old)
    print("check", known[1], f"{width}x{height}", "blocks", used, "match", same)
    if not same:
        raise SystemExit("decoder does not match the verified bromide")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    check_known()
    if args.check_only:
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    jobs = load_jobs(args.limit)
    pending = [job for job in jobs if not os.path.exists(job[4])]
    print("jobs", len(jobs), "pending", len(pending), flush=True)
    ok = 0
    failed = []
    blocks = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for index, (name, width, height, used, error) in enumerate(pool.map(export_one, pending, chunksize=2), 1):
            if error:
                failed.append((name, error))
                print("fail", name, error, flush=True)
            else:
                ok += 1
                blocks.append(used)
            if index % 50 == 0 or index == len(pending):
                print("done", index, "/", len(pending), flush=True)
    print("wrote", ok, "failed", len(failed), "dir", OUT_DIR)
    if blocks:
        print("blocks min", min(blocks), "max", max(blocks))
    if failed:
        print("first failures", failed[:8])


if __name__ == "__main__":
    main()
