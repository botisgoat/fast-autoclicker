"""Generate the Fast Auto Clicker icon (icon.ico + assets/icon.png).

Requires Pillow:  pip install pillow
Run from anywhere:  python assets/make_icon.py
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Catppuccin Mocha palette
BG_TOP = (30, 30, 46)      # base
BG_BOTTOM = (17, 17, 27)   # crust
BORDER = (69, 71, 90)      # surface1
GREEN = (166, 227, 161)    # cursor
INK = (17, 17, 27)         # cursor outline
BURST = (243, 139, 168)    # click burst
TEXT = (205, 214, 244)     # highlight

SS = 4            # supersampling factor
U = 256           # design units
N = U * SS


def s(v):
    return int(round(v * SS))


def render(simple=False):
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))

    # background: rounded square with vertical gradient
    grad = Image.new("RGBA", (N, N))
    gd = ImageDraw.Draw(grad)
    for y in range(N):
        t = y / (N - 1)
        c = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        gd.line([(0, y), (N, y)], fill=c + (255,))
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, N - 1, N - 1], radius=s(56), fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([s(3), s(3), N - 1 - s(3), N - 1 - s(3)], radius=s(53),
                        outline=BORDER + (255,), width=s(6 if simple else 4))

    # small sizes (16/32 px) get a bigger cursor and no speed lines
    tip, k = ((96, 58), 1.12) if simple else ((118, 62), 1.0)

    # speed lines trailing to the left of the cursor
    if not simple:
        for y, x0, x1, a in ((128, 36, 100, 255), (158, 56, 104, 190), (188, 76, 108, 120)):
            d.line([(s(x0), s(y)), (s(x1), s(y))], fill=GREEN + (a,), width=s(13))
            for x in (x0, x1):  # round caps
                r = s(6.5)
                d.ellipse([s(x) - r, s(y) - r, s(x) + r, s(y) + r], fill=GREEN + (a,))

    # click burst around the tip
    rays = ((0, -1), (-1, 0), (-0.72, -0.72), (0.72, -0.72), (-0.72, 0.72))
    r0, r1, w = (20, 44, 11) if not simple else (20, 46, 16)
    for dx, dy in rays:
        p0 = (s(tip[0] + dx * r0), s(tip[1] + dy * r0))
        p1 = (s(tip[0] + dx * r1), s(tip[1] + dy * r1))
        d.line([p0, p1], fill=BURST + (255,), width=s(w))
        for (px, py) in (p0, p1):
            r = s(w / 2)
            d.ellipse([px - r, py - r, px + r, py + r], fill=BURST + (255,))

    # cursor arrow
    shape = [(0, 0), (0, 142), (34, 110), (58, 166), (88, 153), (64, 98), (106, 98)]
    pts = [(s(tip[0] + x * k), s(tip[1] + y * k)) for x, y in shape]
    ow = s(14 if simple else 10)  # dark outline, half of it outside the fill
    d.line(pts + [pts[0], pts[1]], fill=INK + (255,), width=ow, joint="curve")
    for (px, py) in pts:
        d.ellipse([px - ow / 2, py - ow / 2, px + ow / 2, py + ow / 2], fill=INK + (255,))
    d.polygon(pts, fill=GREEN + (255,))

    return img.resize((U, U), Image.LANCZOS)


def main():
    full = render()
    simple = render(simple=True)
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    full.save(os.path.join(ROOT, "assets", "icon.png"))
    sizes = {256: full, 48: full.resize((48, 48), Image.LANCZOS),
             32: simple.resize((32, 32), Image.LANCZOS),
             16: simple.resize((16, 16), Image.LANCZOS)}
    sizes[256].save(os.path.join(ROOT, "icon.ico"), format="ICO",
                    sizes=[(k, k) for k in sizes],
                    append_images=[sizes[48], sizes[32], sizes[16]])


if __name__ == "__main__":
    main()
