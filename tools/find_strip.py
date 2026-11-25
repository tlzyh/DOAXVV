# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

im = np.array(Image.open(r"D:\Projects\YangHui\DOAXVV\export\_phase\sharp_d0.png")).astype(np.int16)
strip = im[:, -16:]
scores = []
width = im.shape[1] - 16
for x in range(width):
    other = im[:, x:x + 16]
    score = float(np.abs(strip - other).mean())
    scores.append((score, x))
scores.sort()
print("best matches for the right 16 columns")
for score, x in scores[:12]:
    print(round(score, 3), x)
neighbor = float(np.abs(strip - im[:, -32:-16]).mean())
print("neighbor", round(neighbor, 3))
