"""
premium_template.py — Template grafico premium con Pillow.
Applicato sempre dopo qualsiasi sfondo (Gemini, stock, fallback locale).
"""
import math
import os
import random
import logging
from pathlib import Path

logger = logging.getLogger('generate_image')

# Palette base
WHITE      = (255, 255, 255)
WHITE_DIM  = (210, 200, 240)
ACCENT     = (160, 130, 240)
MAGENTA    = (220, 60, 140)

FONTS_DIR = Path(__file__).parent.parent / 'public' / 'fonts'

# URL con fallback multipli — prova in ordine fino al primo che funziona
FONT_URLS = {
    'bold': [
        'https://raw.githubusercontent.com/googlefonts/montserrat/master/fonts/ttf/Montserrat-Bold.ttf',
        'https://cdn.jsdelivr.net/gh/googlefonts/montserrat@master/fonts/ttf/Montserrat-Bold.ttf',
    ],
    'regular': [
        'https://raw.githubusercontent.com/googlefonts/montserrat/master/fonts/ttf/Montserrat-Regular.ttf',
        'https://cdn.jsdelivr.net/gh/googlefonts/montserrat@master/fonts/ttf/Montserrat-Regular.ttf',
    ],
    'italic': [
        'https://cdn.jsdelivr.net/gh/googlefonts/montserrat@master/fonts/ttf/Montserrat-Italic.ttf',
        'https://raw.githubusercontent.com/googlefonts/montserrat/master/fonts/ttf/Montserrat-BoldItalic.ttf',
        'https://raw.githubusercontent.com/googlefonts/montserrat/master/fonts/ttf/Montserrat-Bold.ttf',
    ],
}


def ensure_fonts() -> dict:
    import urllib.request
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, urls in FONT_URLS.items():
        dest = FONTS_DIR / f'Montserrat-{name.capitalize()}.ttf'
        if dest.exists():
            paths[name] = str(dest)
            continue
        downloaded = False
        for url in urls:
            try:
                logger.info(f'  Download font {name}...')
                urllib.request.urlretrieve(url, dest)
                logger.info(f'    ✓ Font {name} scaricato')
                downloaded = True
                break
            except Exception as e:
                logger.warning(f'    Font {name} da {url}: {e}')
        paths[name] = str(dest) if downloaded and dest.exists() else None
    return paths


def get_font(fonts: dict, style: str, size: int):
    from PIL import ImageFont
    path = fonts.get(style)
    if path and os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def wrap_text(text: str, font, max_w: int, draw) -> list:
    words = text.split()
    lines, cur = [], ''
    for word in words:
        test = (cur + ' ' + word).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _draw_gradient_overlay(img, c_top=(0, 0, 0, 200), c_bot=(0, 0, 0, 240)):
    """Overlay dark gradient verticale."""
    from PIL import Image, ImageDraw
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    W, H = img.size
    for y in range(H):
        t = y / H
        a = int(c_top[3] + (c_bot[3] - c_top[3]) * t)
        r = int(c_top[0] + (c_bot[0] - c_top[0]) * t)
        g = int(c_top[1] + (c_bot[1] - c_top[1]) * t)
        b = int(c_top[2] + (c_bot[2] - c_top[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b, a))
    return Image.alpha_composite(img.convert('RGBA'), overlay)


def _draw_vignette(img):
    """Vignettatura morbida ai bordi."""
    from PIL import Image, ImageDraw
    vig = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(vig)
    W, H = img.size
    cx, cy = W // 2, H // 2
    steps = 40
    for i in range(steps, 0, -1):
        a = int(160 * (1 - i / steps) ** 2)
        rx = int(cx * i / steps)
        ry = int(cy * i / steps)
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(0, 0, 0, a))
    return Image.alpha_composite(img.convert('RGBA'), vig)


def _draw_glow(draw, cx, cy, r, color, alpha=60):
    steps = max(1, r // 15)
    for i in range(r, 0, -steps):
        a = int(alpha * (i / r) ** 2)
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(*color, a))


def _draw_text_shadow(draw, pos, text, font, fill, offset=(2, 2)):
    x, y = pos
    draw.text((x + offset[0], y + offset[1]), text, font=font,
              fill=(0, 0, 0, 160), anchor='mm')
    draw.text(pos, text, font=font, fill=fill, anchor='mm')


def _local_gradient_bg(W: int, H: int, palette: dict):
    """Genera sfondo gradiente locale premium quando non c'è immagine esterna."""
    from PIL import Image, ImageDraw, ImageFilter
    c1 = palette.get('c1', (8, 6, 25))
    c2 = palette.get('c2', (35, 15, 70))
    c3 = palette.get('c3', (80, 25, 120))
    img = Image.new('RGBA', (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        if t < 0.5:
            t2 = t * 2
            r = int(c1[0] + (c2[0] - c1[0]) * t2)
            g = int(c1[1] + (c2[1] - c1[1]) * t2)
            b = int(c1[2] + (c2[2] - c1[2]) * t2)
        else:
            t2 = (t - 0.5) * 2
            r = int(c2[0] + (c3[0] - c2[0]) * t2)
            g = int(c2[1] + (c3[1] - c2[1]) * t2)
            b = int(c2[2] + (c3[2] - c2[2]) * t2)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # Cerchi glow decorativi
    glow_overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_overlay)
    _draw_glow(gd, int(W * 0.15), int(H * 0.2), 320, c3, 70)
    _draw_glow(gd, int(W * 0.85), int(H * 0.75), 260, c2, 55)
    _draw_glow(gd, int(W * 0.5),  int(H * 0.5),  180, c3, 35)
    img = Image.alpha_composite(img, glow_overlay)

    # Stelle procedurali leggere
    star_overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(star_overlay)
    random.seed(42)
    for _ in range(120):
        sx = random.randint(0, W)
        sy = random.randint(0, int(H * 0.6))
        sr = random.randint(1, 2)
        sa = random.randint(40, 140)
        sd.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 255, 255, sa))
    img = Image.alpha_composite(img, star_overlay)
    return img.convert('RGB')


def _smart_crop(img, target_w: int, target_h: int):
    """Crop centrato generico — usato solo per il template verticale premium."""
    from scripts.smart_crop import smart_vertical_crop
    return smart_vertical_crop(img, target_w, target_h)


def apply_premium_template_vertical(bg_img, ded: dict, fonts: dict,
                                     palette: dict) -> 'Image':
    """
    Applica il template premium 1080x1350 allo sfondo.
    bg_img: PIL.Image RGB o None (usa fallback locale).
    """
    from PIL import Image, ImageDraw, ImageFilter
    W, H = 1080, 1350

    if bg_img is None:
        base = _local_gradient_bg(W, H, palette)
    else:
        base = _smart_crop(bg_img, W, H)
        # Leggero blur di profondità sui bordi
        blurred = base.filter(ImageFilter.GaussianBlur(radius=3))
        mask = Image.new('L', (W, H), 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.ellipse([80, 80, W - 80, H - 80], fill=255)
        base = Image.composite(base, blurred, mask)

    base = _draw_gradient_overlay(
        base.convert('RGBA'),
        c_top=(0, 0, 20, 80),
        c_bot=(0, 0, 10, 230),
    ).convert('RGBA')
    base = _draw_vignette(base)
    draw = ImageDraw.Draw(base)

    # Glow decorativo
    _draw_glow(draw, W // 2, H - 200, 300, (80, 30, 120), 50)

    # Linea decorativa superiore
    for i in range(3):
        draw.line([(60, 90 + i), (W - 60, 90 + i)], fill=(*ACCENT, 180 - i * 40), width=1)

    # Data + giorno
    f_date = get_font(fonts, 'regular', 34)
    date_str = ded.get('date', '')
    day = ded.get('day_name', '')
    date_it = ded.get('date_it', date_str)
    date_text = f'{day.upper()}  ·  {date_it.upper()}' if day else date_it.upper()
    _draw_text_shadow(draw, (W // 2, 140), date_text, f_date, (*ACCENT, 220))

    # Icona musicale
    f_icon = get_font(fonts, 'bold', 70)
    draw.text((W // 2, 240), '♪', font=f_icon, fill=(*WHITE, 35), anchor='mm')

    # Titolo canzone
    f_title = get_font(fonts, 'bold', 76)
    song = ded.get('song_title', '')
    song_lines = wrap_text(song, f_title, W - 120, draw)
    y = 390
    for line in song_lines[:3]:
        _draw_text_shadow(draw, (W // 2, y), line, f_title, WHITE)
        y += 96

    # Artista
    f_artist = get_font(fonts, 'italic', 46)
    _draw_text_shadow(draw, (W // 2, y + 20), ded.get('artist', ''),
                      f_artist, (*MAGENTA, 230))
    y += 90

    # Separatore
    sep_y = y + 50
    draw.line([(W // 2 - 90, sep_y), (W // 2 + 90, sep_y)], fill=(*ACCENT, 140), width=2)

    # Frase breve
    phrase = ded.get('short_phrase', '') or ded.get('dedication_title', '')
    if phrase:
        f_phrase = get_font(fonts, 'italic', 38)
        p_lines = wrap_text(phrase, f_phrase, W - 180, draw)
        y2 = sep_y + 65
        for line in p_lines[:4]:
            _draw_text_shadow(draw, (W // 2, y2), line, f_phrase, (*WHITE_DIM, 200))
            y2 += 54

    # Nome sito
    f_site = get_font(fonts, 'bold', 28)
    site_name = os.environ.get('SITE_NAME', 'DDG FF')
    draw.line([(60, H - 115), (W - 60, H - 115)], fill=(*ACCENT, 90), width=1)
    _draw_text_shadow(draw, (W // 2, H - 80), f'✦ {site_name} ✦', f_site, (*ACCENT, 175))

    return base.convert('RGB')


def apply_premium_template_og(bg_img, ded: dict, fonts: dict,
                               palette: dict) -> 'Image':
    """Applica il template premium 1200x630 (OpenGraph)."""
    from PIL import Image, ImageDraw
    W, H = 1200, 630

    if bg_img is None:
        base = _local_gradient_bg(W, H, palette)
    else:
        from scripts.smart_crop import smart_og_crop
        base = smart_og_crop(bg_img, W, H)

    base = _draw_gradient_overlay(
        base.convert('RGBA'),
        c_top=(0, 0, 20, 100),
        c_bot=(0, 0, 10, 220),
    ).convert('RGBA')
    draw = ImageDraw.Draw(base)

    # Titolo
    f_title = get_font(fonts, 'bold', 68)
    song_lines = wrap_text(ded.get('song_title', ''), f_title, W - 120, draw)
    y = 200
    for line in song_lines[:2]:
        _draw_text_shadow(draw, (W // 2, y), line, f_title, WHITE)
        y += 84

    # Artista
    f_artist = get_font(fonts, 'italic', 42)
    _draw_text_shadow(draw, (W // 2, y + 20), ded.get('artist', ''),
                      f_artist, (*MAGENTA, 220))

    # Data
    f_date = get_font(fonts, 'regular', 28)
    date_it = ded.get('date_it', ded.get('date', ''))
    _draw_text_shadow(draw, (W // 2, H - 70), date_it.upper(), f_date, (*ACCENT, 200))

    # Nome sito a sinistra
    f_site = get_font(fonts, 'bold', 26)
    site_name = os.environ.get('SITE_NAME', 'DDG FF')
    draw.text((70, 55), site_name, font=f_site, fill=(*ACCENT, 200), anchor='lm')

    return base.convert('RGB')
