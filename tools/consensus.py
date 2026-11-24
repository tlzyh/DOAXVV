# -*- coding: utf-8 -*-
import collections
import os

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data\HIGH"
PAIR = bytes.fromhex("4a7b")


def main():
    heads = []
    for name in os.listdir(ROOT):
        full = os.path.join(ROOT, name)
        if os.path.getsize(full) < 64:
            continue
        head = open(full, "rb").read(64)
        if head[4:6] == PAIR:
            heads.append(head)
    print("files", len(heads))
    for index in range(32):
        values = collections.Counter(head[index] for head in heads)
        top, count = values.most_common(1)[0]
        if count >= len(heads) * 0.9:
            print(f"  {index:2} byte {top:02x} in {count}/{len(heads)} unique {len(values)}")
        elif count >= len(heads) * 0.5:
            print(f"  {index:2} mostly {top:02x} {count}/{len(heads)} unique {len(values)}")


if __name__ == "__main__":
    main()
