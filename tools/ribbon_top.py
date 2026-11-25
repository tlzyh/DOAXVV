# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

im = np.array(Image.open(r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_4th_anniversary.png").convert("RGB"))
top = im[:160]
red = (top[:, :, 0] > 160) & (top[:, :, 1] < 90) & (top[:, :, 2] < 90)
white = (top[:, :, 0] > 220) & (top[:, :, 1] > 220) & (top[:, :, 2] > 220)
print("top red/white by 8px")
for x in range(0, 1920, 8):
    print(f"{x:4d} red {red[:, x:x+8].mean():.2f} white {white[:, x:x+8].mean():.2f}")
