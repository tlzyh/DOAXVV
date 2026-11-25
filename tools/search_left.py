# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

def search(path, label):
    im = np.array(Image.open(path).convert("RGB")).astype(np.int16)
    patch = im[80:280, 0:48]
    scores = []
    for x in range(1400, im.shape[1] - 48):
        score = float(np.abs(patch - im[80:280, x:x + 48]).mean())
        scores.append((score, x))
    scores.sort()
    print(label, [(round(s, 2), x) for s, x in scores[:5]])

search(r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_4th_anniversary.png", "anniv")
search(r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_EVENT_NNM_2024_zy_65_b.png", "nnm")
search(r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_AYA_DF_00_A.png", "aya")
search(r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_OWN_ZA_91_A_LUN.png", "lun")
