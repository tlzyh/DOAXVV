# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

im = np.array(Image.open(r"D:\Projects\YangHui\DOAXVV\export\_phase\sharp_d0.png")).astype(int)
# One sample row per block row, the second pixel row inside the block.
rows = im[1::4]
# last k pixels vs first k of same / next / prev
for k in (4, 8, 12, 16):
    last = rows[:, -k:]
    same = np.abs(last - rows[:, :k]).mean()
    nxt = np.abs(last[:-1] - rows[1:, :k]).mean()
    prv = np.abs(last[1:] - rows[:-1, :k]).mean()
    inner = np.abs(last - rows[:, -2 * k:-k]).mean()
    print("k", k, "same", round(float(same), 2), "next", round(float(nxt), 2), "prev", round(float(prv), 2), "inner", round(float(inner), 2))
