# -*- coding: utf-8 -*-
import os
import numpy as np
from PIL import Image

out = r"D:\Projects\YangHui\DOAXVV\export\_phase"
ghost = np.array(Image.open(r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_EVENT_NNM_2024_zy_65_b.png"))
sharp = np.array(Image.open(os.path.join(out, "sharp_d0.png")))


def zoom(image, name, scale=6):
    picture = Image.fromarray(image).resize((image.shape[1] * scale, image.shape[0] * scale), Image.NEAREST)
    picture.save(os.path.join(out, name))


zoom(ghost[0:420, -16:], "ghost_right.png")
zoom(sharp[0:420, -16:], "sharp_right.png")
zoom(ghost[0:420, :16], "ghost_left.png")
# A short full-width band through the blinds and the palm.
band = ghost[120:150]
Image.fromarray(band).resize((1920, 120), Image.NEAREST).save(os.path.join(out, "ghost_band.png"))
band = sharp[120:150]
Image.fromarray(band).resize((1920, 120), Image.NEAREST).save(os.path.join(out, "sharp_band.png"))
print("ok")
