# -*- coding: utf-8 -*-
from PIL import Image

im = Image.open(r"D:\Projects\YangHui\DOAXVV\export\bromide\BROMIDE_AYA_DF_00_A.png")
right = im.crop((1888, 200, 1920, 700))
left = im.crop((0, 200, 32, 700))
right.resize((right.width * 6, right.height * 6), Image.NEAREST).save(r"D:\Projects\YangHui\DOAXVV\export\_phase\aya_right.png")
left.resize((left.width * 6, left.height * 6), Image.NEAREST).save(r"D:\Projects\YangHui\DOAXVV\export\_phase\aya_left.png")
print("ok")
