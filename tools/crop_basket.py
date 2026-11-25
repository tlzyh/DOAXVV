# -*- coding: utf-8 -*-
import os
import numpy as np
from PIL import Image

im = np.array(Image.open(r"D:\Projects\YangHui\DOAXVV\export\_phase\sharp_d0.png"))
# Basket is at the lower right.
crop = im[620:980, 1800:1920]
Image.fromarray(crop).resize((crop.shape[1] * 3, crop.shape[0] * 3), Image.NEAREST).save(
    r"D:\Projects\YangHui\DOAXVV\export\_phase\basket.png"
)
# Top-left blinds and top-right together.
left = im[0:220, 0:80]
right = im[0:220, 1840:1920]
pair = np.concatenate([left, np.full((220, 8, 3), 255, np.uint8), right], axis=1)
Image.fromarray(pair).resize((pair.shape[1] * 3, pair.shape[0] * 3), Image.NEAREST).save(
    r"D:\Projects\YangHui\DOAXVV\export\_phase\pair.png"
)
print("saved", crop.shape)
