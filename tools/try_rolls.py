# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

im = np.array(Image.open(r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_4th_anniversary.png").convert("RGB"))
out = r"D:\Projects\YangHui\DOAXVV\export\_roll"
import os
os.makedirs(out, exist_ok=True)
white = (im[:, :, 0] > 220) & (im[:, :, 1] > 220) & (im[:, :, 2] > 220)
xs = np.arange(1920)
for shift in (0, 64, 96, 112, 120, 128, 144, 160, 176, 192, 208, 224):
    rolled = np.roll(im, shift, axis=1)
    ink = ~(
        (rolled[:, :, 0] > 220) & (rolled[:, :, 1] > 220) & (rolled[:, :, 2] > 220)
    )
    weight = ink.sum(axis=0).astype(float)
    centroid = (weight * xs).sum() / max(weight.sum(), 1)
    right_ink = float(ink[:, -32:].mean())
    left_ink = float(ink[:, :32].mean())
    print(f"shift {shift:4d} centroid {centroid:7.1f} left {left_ink:.3f} right {right_ink:.3f}")
    if shift in (0, 96, 128, 160, 192):
        Image.fromarray(rolled).resize((960, 540), Image.BILINEAR).save(
            os.path.join(out, f"s{shift}.jpg"), quality=80
        )
