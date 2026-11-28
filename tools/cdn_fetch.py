# -*- coding: utf-8 -*-
"""Download costume and hair files the client has not fetched yet from the game CDN.

  python tools\\cdn_fetch.py [--char mis ...] [--hash 61a7a74c ...] [--workers 4] [--dry-run]

The URL of every file follows from the archive directory (out\\archive_dir.csv):

  https://cdn01.doax-venusvacation.jp/production/resource_data/<b>/<folder>/<hash>

where b is the record's resource version (decimal). Targets are all keys in the
cos, hair, chrall and mot rows of out\\chr_data (costume / hair / face TMC and
TMCL, tdpack, char_dat motions, ...; type 59 icons are skipped) that are neither
in the game folders nor already in cdn\\. Files are written to
D:\\Projects\\YangHui\\DOAXVV\\cdn\\<folder>\\<hash> only after their size matches
the record's stored size; reruns skip finished files. The game folder is never
touched. Results go to out\\cdn_fetch.csv.
"""
import argparse
import concurrent.futures
import csv
import os
import subprocess
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "out")
CDN = os.path.join(REPO, "cdn")
GAME = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
URL = "https://cdn01.doax-venusvacation.jp/production/resource_data/%d/%s/%s"
SECTIONS = ("cos", "hair", "chrall", "mot")
SKIP_TYPES = {"59"}


def char_ids(codes):
    wanted = {c.lower() for c in codes}
    ids = set()
    for r in csv.DictReader(open(os.path.join(OUT, "chr_characters.csv"))):
        code = r["code"] or r["face_name"].split("_")[0].lower()
        if code in wanted or r["char_id"] in wanted:
            ids.add(int(r["char_id"]))
    return ids


def targets(args):
    chars = char_ids(args.char) if args.char else None
    hashes = set()
    for section in SECTIONS:
        for r in csv.DictReader(open(os.path.join(OUT, "chr_data", section + ".csv"))):
            if chars is not None and int(r["id"], 16) & 0xFFFF not in chars:
                continue
            for key, w in r.items():
                if key.startswith("w") and w and ":" in w and w.partition(":")[0] not in SKIP_TYPES:
                    hashes.add(w.rpartition("/")[2])
    if args.hash:
        hashes = {h for h in hashes if any(h.startswith(p) for p in args.hash)} if chars is not None else \
            {r["hash"] for r in csv.DictReader(open(os.path.join(OUT, "archive_dir.csv"), encoding="utf-8"))
             if any(r["hash"].startswith(p) for p in args.hash)}
    out = []
    for r in csv.DictReader(open(os.path.join(OUT, "archive_dir.csv"), encoding="utf-8")):
        if r["hash"] not in hashes:
            continue
        folder = r["folder"]
        if any(os.path.exists(os.path.join(GAME, sub, folder, r["hash"])) for sub in ("", "DL")):
            continue
        have = os.path.join(CDN, folder, r["hash"])
        if os.path.exists(have) and os.path.getsize(have) == int(r["stored"]):
            continue
        out.append((int(r["b"], 16), folder, r["hash"], int(r["stored"])))
    return sorted(set(out))


def fetch(item, retries=3):
    """curl.exe, because Python's TLS reads from this CDN run at a tenth of curl's speed."""
    version, folder, name, size = item
    path = os.path.join(CDN, folder, name)
    if os.path.exists(path) and os.path.getsize(path) == size:
        return item, "have"
    url = URL % (version, folder, name)
    tmp = path + ".part"
    error = ""
    for attempt in range(retries):
        proc = subprocess.run(["curl.exe", "-s", "-S", "-f", "--max-time", "600", "-o", tmp, url],
                              capture_output=True, text=True)
        if proc.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) == size:
            os.replace(tmp, path)
            return item, "ok"
        error = proc.stderr.strip() or "size %d != %d" % (os.path.getsize(tmp) if os.path.exists(tmp) else -1, size)
        if "404" in error:
            break
        time.sleep(2 * (attempt + 1))
    if os.path.exists(tmp):
        os.remove(tmp)
    return item, "error: " + error


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--char", action="append", default=[], help="character code or id (repeatable)")
    ap.add_argument("--hash", action="append", default=[], help="file hash prefix (repeatable)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    items = targets(args)
    total = sum(item[3] for item in items)
    print("files", len(items), "GB %.2f" % (total / 1e9), flush=True)
    if args.dry_run or not items:
        return
    for folder in {item[1] for item in items}:
        os.makedirs(os.path.join(CDN, folder), exist_ok=True)
    results, done_bytes, start = [], 0, time.time()
    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        for n, (item, status) in enumerate(pool.map(fetch, items), 1):
            results.append((item[1], item[2], item[0], item[3], status))
            done_bytes += item[3]
            if n % 200 == 0 or n == len(items):
                rate = done_bytes / max(time.time() - start, 1) / 1e6
                print("files %d/%d  %.2f/%.2f GB  %.1f MB/s  errors %d" % (
                    n, len(items), done_bytes / 1e9, total / 1e9, rate,
                    sum(1 for r in results if r[4].startswith("error"))), flush=True)
    with open(os.path.join(OUT, "cdn_fetch.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("folder", "hash", "version", "size", "result"))
        w.writerows(results)


if __name__ == "__main__":
    main()
