# -*- coding: utf-8 -*-
import collections
import csv
import re

rows = list(csv.DictReader(open(r"D:\Projects\YangHui\DOAXVV\index.csv", encoding="utf-8")))
known = [row for row in rows if row["magic"]]
print("known", len(known), "of", len(rows))


def show(title, pred, limit=6):
    hit = [row for row in known if pred(row)]
    print(f"\n{title} {len(hit)}")
    for row in hit[:limit]:
        print(f"  {row['magic']:10} {int(row['size']):8d} {row['name'][:52]:52} {row['folder']}")


show("hair", lambda row: row["magic"] == "TMC" and "hair" in row["name"].lower())
show("za", lambda row: row["magic"] == "TMC" and re.search(r"(^|_)za_", row["name"], re.I))
show("clip", lambda row: row["magic"] == "clip")
show("face", lambda row: row["magic"] == "TMC" and "face" in row["name"].lower())
show("dds", lambda row: row["magic"] == "DDS")
show("scene", lambda row: row["magic"] == "SCENE" and "CMU" in row["name"])
# animation-like names of any type
show(
    "mot/anim name",
    lambda row: re.search(r"anim|motion|skel|\.g1a|mot_", row["name"], re.I),
)
print("\nmagic totals")
for magic, count in collections.Counter(row["magic"] for row in known).most_common(15):
    print(f"  {count:6d} {magic}")
