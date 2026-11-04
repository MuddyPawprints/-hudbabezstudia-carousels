#!/usr/bin/env python3
"""Fotkový carousel @hudbabezstudia (formát podle vzoru „Peklo jedné smyčky“).

Použití: python3 render_foto.py cfg.json outdir
cfg = {
  "paras": ["titulek", "slide 2", ..., "CTA"],   # každý odstavec = jeden slide
  "photos": ["/cesta/fotka1.jpg", ...],          # 1 fotka = na všech slidech;
                                                 # víc fotek = slide i dostane photos[min(i, n-1)]
  "photo_for_slide": [0,0,1,...],                # volitelně: index fotky pro každý slide
  "focus": [0.5, 0.5]                            # volitelně: střed ořezu (x, y) 0–1
}
Fotka se ořízne na 1080x1174 (cover), překryje se černým fadem změřeným ze vzoru,
pod ní je plná černá. Text bílý Montserrat Bold, centrovaný.
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
BOLD = os.path.join(FONTS, "Montserrat-Bold.ttf")
BOLDIT = os.path.join(FONTS, "Montserrat-BoldItalic.ttf")  # text mezi * * = kurzíva (Claudova slova)
_IT = {}


def ital(font):
    k = font.size
    if k not in _IT:
        _IT[k] = ImageFont.truetype(BOLDIT, font.size)
    return _IT[k]


def segs(l, it):
    """Rozdělí řádek podle * na úseky (text, kurzíva?); vrátí i stav na konci řádku."""
    out = []
    for k, part in enumerate(l.split("*")):
        if k:
            it = not it
        if part:
            out.append((part, it))
    return out, it


def mlen(font, l, it=False):
    return sum((ital(font) if i else font).getlength(t) for t, i in segs(l, it)[0])


def mtext(d, xy, l, font, it, **kw):
    x, y = xy
    for t, i in segs(l, it)[0]:
        f = ital(font) if i else font
        d.text((x, y), t, font=f, **kw)
        x += f.getlength(t)
    return segs(l, it)[1]
FOOT = os.path.join(FONTS, "Inter-Regular.otf")
if not os.path.exists(FOOT):
    FOOT = "/usr/share/fonts/opentype/inter/Inter-Regular.otf"

W, H = 1080, 1350
PHOTO_H = 1174  # fotka končí tady, pod ní plná černá
# fade naměřený ze vzoru: (y, násobek jasu)
FADE = [(0, 1.0), (180, 1.0), (200, .979), (250, .959), (300, .938), (350, .904),
        (400, .863), (450, .822), (500, .767), (550, .705), (600, .644), (650, .575),
        (700, .5), (750, .432), (800, .363), (850, .295), (900, .233), (950, .178),
        (1000, .137), (1050, .096), (1100, .062), (1150, .041), (1173, .028)]

TITLE = dict(size=75, pitch=105, maxw=560)
BODY = dict(size=41, pitch=58.5, maxw=830)
CTA = dict(size=75, pitch=105, maxw=860)  # CTA vždy velké jako titulek (user 2026-11-03)
SINGLE = set("kKsSvVzZaAiIoOuU")  # jednopísmenné předložky/spojky nesmí končit řádek


def fade_layer():
    ys = np.arange(PHOTO_H)
    k = np.interp(ys, [p[0] for p in FADE], [p[1] for p in FADE])
    return k[:, None, None]


def cover(img, w, h, focus=(0.5, 0.5)):
    img = ImageOps.exif_transpose(img).convert("RGB")
    s = max(w / img.width, h / img.height)
    nw, nh = round(img.width * s), round(img.height * s)
    img = img.resize((nw, nh), Image.LANCZOS)
    x = int((nw - w) * focus[0]); y = int((nh - h) * focus[1])
    return img.crop((x, y, x + w, y + h))


def background(photo, focus):
    bg = Image.new("RGB", (W, H), (0, 0, 0))
    p = np.asarray(cover(photo, W, PHOTO_H, focus)).astype(float) * fade_layer()
    bg.paste(Image.fromarray(np.clip(p, 0, 255).astype("uint8")), (0, 0))
    return bg


def wrap(text, font, maxw):
    words = text.split()
    lines, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        if cur and mlen(font, trial) > maxw:
            # jednopísmenné slovo na konci řádku přesuň na další
            carry = []
            while len(cur) > 1 and len(cur[-1]) == 1 and cur[-1] in SINGLE:
                carry.insert(0, cur.pop())
            lines.append(" ".join(cur)); cur = carry + [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    # pomlčka nesmí začínat řádek
    for i in range(1, len(lines)):
        if lines[i].startswith(("–", "-")):
            first, _, rest = lines[i].partition(" ")
            lines[i - 1] += " " + first; lines[i] = rest
    return [l for l in lines if l]


def balance(text, font, maxw):
    """Vyrovnané řádky (jako u titulku/CTA ve vzoru): zkus užší šířku se stejným počtem řádků."""
    base = wrap(text, font, maxw)
    best = base
    for w in range(int(maxw), 300, -10):
        l = wrap(text, font, w)
        if len(l) != len(base):
            break
        best = l
    return best


def draw_lines(img, lines, font, pitch, center_y=None, bottom_y=None, shadow=False):
    asc, desc = font.getmetrics()
    n = len(lines)
    # vertikální rozsah počítáme podle výšky verzálek, jako měření ze vzoru
    cap = font.getbbox("H")[1]
    capb = font.getbbox("H")[3]
    block_top_off = cap
    block_h = (n - 1) * pitch + (capb - cap)
    if center_y is not None:
        top = center_y - block_h / 2 - block_top_off
    else:
        top = bottom_y - block_h - block_top_off
    # dlouhý text nesmí zajet do patičky: spodek bloku max. y=1190
    if top + block_top_off + block_h > 1190:
        top = 1190 - block_h - block_top_off
    if shadow:
        sh = Image.new("L", img.size, 0)
        sd = ImageDraw.Draw(sh)
        it = False
        for i, l in enumerate(lines):
            x = (W - mlen(font, l, it)) / 2
            it = mtext(sd, (x, top + i * pitch + 3), l, font, it, fill=150)
        sh = sh.filter(ImageFilter.GaussianBlur(10))
        img.paste((0, 0, 0), (0, 0), sh)
    d = ImageDraw.Draw(img)
    it = False
    for i, l in enumerate(lines):
        x = (W - mlen(font, l, it)) / 2
        it = mtext(d, (x, top + i * pitch), l, font, it, fill=(255, 255, 255))


def chevrons(img):
    d = ImageDraw.Draw(img)
    cy, hh, ww, lw = 1152, 47, 47, 13  # výška ramene, šířka, tloušťka
    for i, g in enumerate([105, 180, 255]):
        x0 = 469 + i * 47
        pts = [(x0, cy - hh), (x0 + ww, cy), (x0, cy + hh)]
        d.line(pts, fill=(g, g, g), width=lw, joint="curve")
        for p in pts:
            r = lw / 2
            d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=(g, g, g))


def progress(img, i, n):
    """Čtverečky postupu (jako u barevných karuselů): 14 px, mezera 12, horní hrana y=1236."""
    d = ImageDraw.Draw(img)
    sz, gap, y = 14, 12, 1236
    x = (W - (n * sz + (n - 1) * gap)) / 2
    for k in range(n):
        box = (x, y, x + sz - 1, y + sz - 1)
        if k == i:
            d.rectangle(box, fill=(255, 255, 255))
        else:
            d.rectangle(box, outline=(255, 255, 255), width=2)
        x += sz + gap


def footer(img):
    f = ImageFont.truetype(FOOT, 29)
    d = ImageDraw.Draw(img)
    t = "@hudbabezstudia"
    d.text(((W - f.getlength(t)) / 2, 1305), t, font=f, fill=(255, 255, 255), anchor="ls")


def main(cfg_path, out):
    cfg = json.load(open(cfg_path))
    base = os.path.dirname(os.path.abspath(cfg_path))
    photos = [Image.open(os.path.join(base, p)) for p in cfg["photos"]]
    paras = [p.strip() for p in cfg["paras"] if p.strip()]
    focus = tuple(cfg.get("focus", (0.5, 0.5)))
    pmap = cfg.get("photo_for_slide") or [min(i, len(photos) - 1) for i in range(len(paras))]
    os.makedirs(out, exist_ok=True)
    n = len(paras)
    for i, text in enumerate(paras):
        img = background(photos[pmap[i]], focus)
        if i == 0:
            s = TITLE; f = ImageFont.truetype(BOLD, s["size"])
            lines = wrap(text, f, s["maxw"])
            draw_lines(img, lines, f, s["pitch"], bottom_y=1003, shadow=True)
            chevrons(img)
        elif i == n - 1:
            s = CTA; f = ImageFont.truetype(BOLD, s["size"])
            lines = balance(text, f, s["maxw"])
            draw_lines(img, lines, f, s["pitch"], center_y=1000, shadow=True)
        else:
            s = BODY; f = ImageFont.truetype(BOLD, s["size"])
            lines = wrap(text, f, s["maxw"])
            draw_lines(img, lines, f, s["pitch"], center_y=1049, shadow=True)
            progress(img, i, n)
        footer(img)
        img.save(os.path.join(out, f"{i + 1}.png"))
    print("ok", n)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
