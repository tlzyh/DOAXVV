# -*- coding: utf-8 -*-
import os
import numpy as np
from PIL import Image

folder = r"D:\Projects\YangHui\DOAXVV\export\bromide"
for name in (
    "BROMIDE_OWN_ZA_91_A_LUN.png",
    "BROMIDE_MIS_ZA_16_A.png",
    "BROMIDE_AYA_DF_00_A.png",
    "BROMIDE_EVENT_NNM_2024_zy_65_b.png",
):
    im = np.array(Image.open(os.path.join(folder, name))).astype(int)
    rows = im[1::4]
    print(name)
    for k in (4, 8):
        last = rows[:, -k:]
        same = np.abs(last - rows[:, :k]).mean()
        nxt = np.abs(last[:-1] - rows[1:, :k]).mean()
        inner = np.abs(last - rows[:, -2 * k:-k]).mean()
        print("  k", k, "same", round(float(same), 2), "next", round(float(nxt), 2), "inner", round(float(inner), 2))
