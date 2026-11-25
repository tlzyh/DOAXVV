# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

im = np.array(Image.open(r"D:\Projects\YangHui\DOAXVV\export\_phase\sharp_d0.png")).astype(int)
lum = im.mean(axis=2)
for y in (200, 400, 800, 900):
    row = lum[y]
    print("y", y)
    print("  first", [int(v) for v in row[:12]])
    print("  last ", [int(v) for v in row[-12:]])
    print("  next4 first", [int(v) for v in lum[y + 4, :12]])
