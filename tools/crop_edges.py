# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

src = r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_EVENT_NNM_2024_zy_65_b.png"
out = r"D:\Projects\YangHui\DOAXVV\export\_phase"
im = np.array(Image.open(src))


def save(name, crop, scale=4):
    image = Image.fromarray(crop).resize((crop.shape[1] * scale, crop.shape[0] * scale), Image.NEAREST)
    image.save(out + "\\" + name)


save("left.png", im[200:700, :48])
save("right.png", im[200:700, -48:])
save("bottle.png", im[250:520, 980:1220], 2)
save("face.png", im[80:360, 250:560], 2)
print("saved")
