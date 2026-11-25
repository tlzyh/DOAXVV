# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

im = np.array(Image.open(r"D:\Projects\YangHui\DOAXVV\export\_phase\sharp_d0.png")).astype(float)
# Vertical profile through the blinds.
left = im[50:200, 0:16].mean(axis=(1, 2))
right = im[50:200, -16:].mean(axis=(1, 2))
wall = im[50:200, 1500:1516].mean(axis=(1, 2))


def corr(a, b):
    a = a - a.mean()
    b = b - b.mean()
    return float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-9))


print("left energy", round(float(left.std()), 2), "right", round(float(right.std()), 2), "wall", round(float(wall.std()), 2))
print("corr left-right", round(corr(left, right), 3), "left-wall", round(corr(left, wall), 3))
# Does the right edge oscillate every few rows like blinds?
print("left profile", [round(v, 1) for v in left[::8]])
print("right profile", [round(v, 1) for v in right[::8]])
