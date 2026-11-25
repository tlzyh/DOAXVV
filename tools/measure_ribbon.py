# -*- coding: utf-8 -*-
"""Find how wide the misplaced right-hand ribbon is."""
import numpy as np
from PIL import Image

path = r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_4th_anniversary.png"
im = np.array(Image.open(path).convert("RGB"))
red = (im[:, :, 0] > 160) & (im[:, :, 1] < 90) & (im[:, :, 2] < 90)
cols = red.mean(axis=0)
print("shape", im.shape)
print("red fraction by 16px buckets")
for x in range(0, 1920, 16):
    frac = float(cols[x:x + 16].mean())
    if frac > 0.01:
        print(f"  {x:4d} {frac:.3f}")
# Rightmost columns that are red anywhere.
right = np.where(cols > 0.002)[0]
print("last red columns", right[-20:] if len(right) else None)
print("first red columns", right[:20] if len(right) else None)
