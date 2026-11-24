# -*- coding: utf-8 -*-
import csv
import re

rows = list(csv.DictReader(open(r"D:\Projects\YangHui\DOAXVV\index.csv", encoding="utf-8")))
known = [row for row in rows if row["magic"]]


def show(title, pred, limit=8):
    hit = [row for row in known if pred(row)]
    print(f"\n{title} {len(hit)}")
    for row in hit[:limit]:
        print(f"  {row['magic']:10} {int(row['size']):8d} {row['name'][:56]:56} {row['folder']}")


show("SCENE", lambda row: row["magic"] == "SCENE")
show(
    "SCENE cmu/cnt/eve",
    lambda row: row["magic"] == "SCENE" and re.search(r"CMU|CNT_|EVE_|IBL", row["name"]),
)
show(
    "bromide",
    lambda row: "BROMIDE" in row["name"].upper() or "bromide" in row["name"],
)
show(
    "swimsuit photo",
    lambda row: re.search(r"PHOTO.*ZA_|ZA_.*PHOTO|chara_still|still", row["name"], re.I),
)
show(
    "misaki photo or bromide",
    lambda row: re.search(r"MIS", row["name"]) and re.search(r"PHOTO|BROMIDE|still|pic", row["name"], re.I),
)
