# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

im = np.array(Image.open(r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_EVENT_NNM_2024_zy_65_b.png"))
print("size", im.shape)
for span in (4, 8, 12, 16, 32):
    right = im[:, -span:].astype(int)
    best = None
    for dy in range(-16, 17):
        left = np.roll(im[:, :span], dy, axis=0).astype(int)
        score = np.abs(right - left).mean()
        if best is None or score < best[0]:
            best = (score, dy)
    print("span", span, "best dy", best[1], "mean", round(best[0], 3), "dy0", round(float(np.abs(right - im[:, :span].astype(int)).mean()), 3))

# Is the right strip the left of the following block-row?
for span in (4, 8, 16):
    right = im[:-4, -span:].astype(int)
    left_next = im[4:, :span].astype(int)
    print("span", span, "right vs next-row left", round(float(np.abs(right - left_next).mean()), 3)))
