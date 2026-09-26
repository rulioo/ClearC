"""生成磁盘（硬盘）图标 app.ico（多尺寸），供 PyInstaller --icon 打包使用。

画法：蓝色圆角矩形机身 + 浅蓝面板 + 冰蓝盘片 + 绿色状态灯 + 底部白色散热槽。
运行：python tools/make_icon.py
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

SIZE = 256
BLUE = (47, 111, 237)  # 主蓝 #2F6FED
BLUE_LT = (77, 139, 245)  # 面板浅蓝 #4D8BF5
GREEN = (52, 211, 92)  # 状态灯 #34D353
WHITE = (255, 255, 255)
ICE = (234, 241, 254)  # 盘片浅冰蓝 #EAF1FE


def rounded_rect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def make_icon() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 硬盘机身（圆角矩形，主蓝）
    rounded_rect(d, (28, 44, 228, 212), 34, BLUE)
    # 前面板（浅蓝内嵌）
    rounded_rect(d, (44, 60, 212, 196), 22, BLUE_LT)

    # 盘片（顶部中央：冰蓝圆盘 + 蓝色主轴）
    d.ellipse((84, 82, 148, 146), fill=ICE)
    d.ellipse((112, 110, 120, 118), fill=BLUE)

    # 状态灯（右上角绿色）
    d.ellipse((176, 70, 190, 84), fill=GREEN)

    # 散热槽（底部 3 条白色圆角条）
    for y in (160, 172, 184):
        rounded_rect(d, (60, y, 172, y + 8), 4, WHITE)

    return img


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon = make_icon()
    icon.save(
        os.path.join(root, "app.ico"),
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    icon.save(os.path.join(root, "app_icon.png"))
    print("app.ico + app_icon.png written")
