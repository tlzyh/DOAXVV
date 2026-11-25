# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

im = np.array(Image.open(r"D:\Projects\YangHui\DOAXVV\export\_phase\sharp_d0.png")).astype(float)
lum = im[760:900].mean(axis=2).mean(axis=0)
segment = lum[1400:1880]
best = None
for period in range(4, 48):
    err = np.abs(segment[period:] - segment[:-period]).mean()
    if best is None or err < best[0]:
        best = (err, period)
print("period", best)
period = best[1]
err = np.abs(lum[period:] - lum[:-period])
print("tail errors")
for x in range(1860, 1920):
    print(x, round(float(err[x - period]), 2), "lum", round(float(lum[x]), 1), "pred", round(float(lum[x - period]), 1))
