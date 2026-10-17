"""Draws the app icon (same design as ui/icon.svg) as a multi-size Windows .ico."""
from pathlib import Path

from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
k = S / 64
d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(14 * k), fill=(47, 91, 183, 255))
d.arc([14 * k, 22 * k, 50 * k, 58 * k], start=180, end=360, fill=(255, 255, 255, 255), width=int(5 * k))
d.ellipse([27 * k, 35 * k, 37 * k, 45 * k], fill=(255, 255, 255, 255))
d.rounded_rectangle([12 * k, 44 * k, 52 * k, 50 * k], radius=int(3 * k), fill=(159, 192, 255, 255))
out = Path(__file__).with_name("icon.ico")
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote", out)
