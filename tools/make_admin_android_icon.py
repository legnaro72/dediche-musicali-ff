from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "public" / "icons" / "icon-512.png"
OUT_DIR = ROOT / "android-streamlit-admin" / "app" / "src" / "main" / "res" / "drawable-nodpi"
OUT = OUT_DIR / "ic_launcher_admin.png"


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbi.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def gradient_text(text: str, font: ImageFont.FreeTypeFont, stroke: int = 3) -> Image.Image:
    probe = Image.new("L", (1, 1), 0)
    draw = ImageDraw.Draw(probe)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    width = bbox[2] - bbox[0] + 26
    height = bbox[3] - bbox[1] + 22
    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.text((13 - bbox[0], 9 - bbox[1]), text, font=font, fill=255, stroke_width=stroke, stroke_fill=255)

    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    grad_px = gradient.load()
    top = (255, 250, 184)
    mid = (245, 181, 48)
    bottom = (126, 72, 9)
    for y in range(height):
        t = y / max(1, height - 1)
        if t < 0.45:
            local = t / 0.45
            color = tuple(round(top[i] * (1 - local) + mid[i] * local) for i in range(3))
        else:
            local = (t - 0.45) / 0.55
            color = tuple(round(mid[i] * (1 - local) + bottom[i] * local) for i in range(3))
        for x in range(width):
            grad_px[x, y] = (*color, mask.getpixel((x, y)))

    highlight = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    highlight_draw = ImageDraw.Draw(highlight)
    highlight_draw.text(
        (13 - bbox[0] - 1, 9 - bbox[1] - 2),
        text,
        font=font,
        fill=(255, 255, 240, 150),
        stroke_width=1,
        stroke_fill=(255, 255, 240, 110),
    )
    gradient.alpha_composite(highlight)
    return gradient


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = Image.open(SOURCE).convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shade = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shade_px = shade.load()
    for y in range(282, 512):
        alpha = min(232, int((y - 282) / 230 * 232))
        for x in range(512):
            shade_px[x, y] = (5, 10, 28, alpha)
    overlay.alpha_composite(shade.filter(ImageFilter.GaussianBlur(10)))

    old_text_cover = Image.new("RGBA", (468, 156), (0, 0, 0, 0))
    cover_draw = ImageDraw.Draw(old_text_cover)
    cover_draw.rounded_rectangle(
        (0, 6, 468, 150),
        radius=42,
        fill=(5, 12, 35, 222),
    )
    old_text_cover = old_text_cover.filter(ImageFilter.GaussianBlur(9))
    overlay.alpha_composite(old_text_cover, (22, 326))

    font = load_font(86)
    text = gradient_text("ADMIN FF", font, stroke=3)
    text = text.transform(
        (text.width + 64, text.height),
        Image.Transform.AFFINE,
        (1, -0.34, 48, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )

    shadow = Image.new("RGBA", text.size, (0, 0, 0, 0))
    shadow.alpha_composite(text)
    shadow = shadow.filter(ImageFilter.GaussianBlur(5))
    shadow_pixels = shadow.load()
    for y in range(shadow.height):
        for x in range(shadow.width):
            alpha = shadow_pixels[x, y][3]
            shadow_pixels[x, y] = (0, 0, 0, min(180, alpha))

    x = 36
    y = 358
    overlay.alpha_composite(shadow, (x + 9, y + 13))
    overlay.alpha_composite(text, (x, y))

    result = Image.alpha_composite(base, overlay)
    result.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
