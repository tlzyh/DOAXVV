# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

im = np.array(Image.open(r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_4th_anniversary.png").convert("RGB"))
white = (im[:, :, 0] > 220) & (im[:, :, 1] > 220) & (im[:, :, 2] > 220)
ink = ~white
xs = np.arange(1920)
# centroid of non-white pixels
weight = ink.sum(axis=0).astype(float)
centroid = (weight * xs).sum() / weight.sum()
print("centroid", round(float(centroid), 1), "center", 960)
# How much right-edge content is non-white in the outer margin
for edge in (32, 64, 96, 128, 160, 192, 224, 256):
    print("right", edge, "ink", round(float(ink[:, -edge:].mean()), 3), "left", round(float(ink[:, :edge].mean()), 3))
