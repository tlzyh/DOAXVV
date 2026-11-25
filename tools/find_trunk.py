# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

for label, path in (
    ("ghost", r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_EVENT_NNM_2024_zy_65_b.png"),
    ("sharp", r"D:\Projects\YangHui\DOAXVV\export\_phase\sharp_d0.png"),
):
    im = np.array(Image.open(path)).astype(np.int16)
    trunk = im[100:500, 1760:1784]
    scores = []
    for x in range(0, im.shape[1] - 24, 4):
        score = float(np.abs(trunk - im[100:500, x:x + 24]).mean())
        scores.append((score, x))
    scores.sort()
    print(label, [(round(s, 2), x) for s, x in scores[:6]])
