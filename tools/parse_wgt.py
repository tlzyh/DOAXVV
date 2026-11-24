# -*- coding: utf-8 -*-
import os
import zlib

SEED = open(r"D:\Projects\YangHui\DOAXVV\tools\_seed_live.bin", "rb").read()
ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"
PREFIX = "0178ffdc03db588d"
KEY = bytes.fromhex("288548")


def apply(data):
    out = bytearray(len(data))
    for i, value in enumerate(data):
        mixed = SEED[i % len(SEED)] ^ KEY[i % len(KEY)]
        out[i] = value if value == 0 or value == mixed else value ^ mixed
    return bytes(out)


def pages(plain):
    pos = 0
    out = []
    while pos + 8 <= len(plain) and len(out) < 30:
        if plain[pos + 4:pos + 6] not in (b"\x78\x9c", b"\x78\xda"):
            nxt = (pos + 16) & ~15
            if nxt <= pos or nxt + 6 > len(plain) or plain[nxt + 4:nxt + 6] not in (b"\x78\x9c", b"\x78\xda"):
                break
            pos = nxt
            continue
        obj = zlib.decompressobj()
        inflated = obj.decompress(plain[pos + 4:]) + obj.flush()
        used = len(plain) - pos - 4 - len(obj.unused_data)
        out.append(inflated)
        pos = (pos + 4 + used + 15) & ~15
    return out


def strings(blob):
    found = []
    cur = bytearray()
    start = 0
    for i, value in enumerate(blob):
        if 32 <= value < 127:
            if not cur:
                start = i
            cur.append(value)
        else:
            if len(cur) >= 4 and any(chr(b).isalpha() for b in cur):
                found.append((start, cur.decode("ascii")))
            cur.clear()
    return found


def main():
    for name in os.listdir(ROOT):
        if name.startswith(PREFIX):
            data = open(os.path.join(ROOT, name), "rb").read()
            break
    plain = apply(data)
    chunks = pages(plain)
    print("file", len(data), "pages", [(i, len(c), c[:8]) for i, c in enumerate(chunks)])
    blob = chunks[0]
    print("strings:")
    for pos, text in strings(blob):
        if text.replace("_", "").isalnum():
            print(f"  {pos:#x} {text}")
    open(r"D:\Projects\YangHui\DOAXVV\tools\_wgt_body.bin", "wb").write(b"".join(chunks))
    print("wrote", sum(len(c) for c in chunks))


if __name__ == "__main__":
    main()
