# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

path = r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_EVENT_NNM_2024_zy_65_b.png"
im = np.array(Image.open(path)).astype(np.int16)
patch = im[40:120, 0:32]
scores = []
for x in range(0, im.shape[1] - 32, 2):
    for y in (0, 20, 40, 60):
        window = im[y:y + 80, x:x + 32]
        score = float(np.abs(patch - window).mean())
        scores.append((score, x, y))
scores.sort()
print("blind-patch matches")
for score, x, y in scores[:15]:
    print(round(score, 2), "x", x, "y", y)

strip = im[:, -24:]
col_scores = []
for x in range(0, im.shape[1] - 24, 2):
    window = im[:, x:x + 24]
    score = float(np.abs(strip - window).mean())
    col_scores.append((score, x))
col_scores.sort()
print("right 24-col matches")
for score, x in col_scores[:10]:
    print(round(score, 2), x)
