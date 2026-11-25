# -*- coding: utf-8 -*-
import os
import numpy as np
from PIL import Image

folder = r"D:\Projects\YangHui\DOAXVV\export\bromide"
names = [
    "BROMIDE_4th_anniversary.png",
    "BROMIDE_5th_anniversary.png",
    "BROMIDE_6th_anniversary.png",
    "BROMIDE_EVENT_NNM_2024_zy_65_b.png",
    "BROMIDE_AYA_DF_00_A.png",
    "BROMIDE_OWN_ZA_91_A_LUN.png",
    "BROMIDE_MIS_ZA_16_A.png",
]
for name in names:
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        print("missing", name)
        continue
    im = np.array(Image.open(path).convert("RGB")).astype(int)
    jump = np.abs(im[:, 1:] - im[:, :-1]).mean(axis=(0, 2))
    # Strongest seams, ignoring the leftmost 200 (subject edges).
    order = np.argsort(jump)[::-1]
    top = [(int(i + 1), round(float(jump[i]), 1)) for i in order[:6]]
    print(name[:28], top)
