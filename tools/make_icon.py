"""Draws the AI Animator icon: an eye inside a film frame, crimson on near-black.
Run: python tools/make_icon.py  -> ai_animator/resources/icon.png + icon.ico"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

S = 1024
OUT = Path(__file__).resolve().parent.parent / "ai_animator" / "resources"
RED, DARK = (214, 64, 78), (18, 18, 22)

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([40, 40, S - 40, S - 40], radius=200, fill=DARK, outline=(48, 48, 58), width=12)
# film sprocket holes
for y in range(170, S - 170, 110):
    for x in (110, S - 160):
        d.rounded_rectangle([x, y, x + 50, y + 62], radius=12, fill=(44, 44, 54))
# glow
glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(glow).ellipse([250, 330, S - 250, S - 330], fill=RED + (150,))
img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(60)))
d = ImageDraw.Draw(img)
# eye: almond = intersection of two big circles
m1, m2 = Image.new("L", (S, S), 0), Image.new("L", (S, S), 0)
ImageDraw.Draw(m1).ellipse([S // 2 - 420, 300, S // 2 + 420, 300 + 840], fill=255)
ImageDraw.Draw(m2).ellipse([S // 2 - 420, 724 - 840, S // 2 + 420, 724], fill=255)
from PIL import ImageChops
almond = ImageChops.multiply(m1, m2)
img.paste((235, 232, 226, 255), (0, 0), almond)
d = ImageDraw.Draw(img)
d.ellipse([382, 382, 642, 642], fill=RED)
d.ellipse([450, 450, 574, 574], fill=(14, 10, 12))
d.ellipse([470, 430, 520, 480], fill=(255, 255, 255))
# brush stroke under the eye (the "draw" part)
pts = []
for i in range(41):  # quadratic bezier, tapered "brush" stroke
    t = i / 40
    x = (1 - t) ** 2 * 280 + 2 * (1 - t) * t * 512 + t ** 2 * 744
    y = (1 - t) ** 2 * 790 + 2 * (1 - t) * t * 870 + t ** 2 * 790
    pts.append((x, y))
for i, (x, y) in enumerate(pts):
    r = 6 + 16 * (1 - abs(i - 20) / 20)
    d.ellipse([x - r, y - r, x + r, y + r], fill=RED)

OUT.mkdir(parents=True, exist_ok=True)
img.resize((512, 512), Image.LANCZOS).save(OUT / "icon.png")
img.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon written to", OUT)
