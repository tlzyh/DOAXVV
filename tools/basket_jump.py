# -*- coding: utf-8 -*-
import os
import numpy as np
from PIL import Image

out = r"D:\Projects\YangHui\DOAXVV\export\_phase"
for name in ("sharp_d0", "sharp_d1", "sharp_d-1"):
    im = np.array(Image.open(os.path.join(out, name + ".png")))
    crop = im[700:980, 1860:1920]
    Image.fromarray(crop).resize((crop.shape[1] * 6, crop.shape[0] * 6), Image.NEAREST).save(
        os.path.join(out, name + "_basket.png")
    )
# Where the weave breaks: column difference inside the basket band.
im = np.array(Image.open(os.path.join(out, "sharp_d0.png"))).astype(int)
band = im[760:900]
jump = np.abs(band[:, 1:] - band[:, :-1]).mean(axis=(0, 2))
print("basket jumps near the right")
for x in range(1840, 1919):
    if jump[x] > 8:
        print(x + 1, round(float(jump[x]), 2))
