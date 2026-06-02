"""
raw_image_handler.py — Gestisce image_mode=raw.
Nessun overlay, nessuna tipografia, solo crop/resize/WebP.
Supporta file locali e URL HTTPS remoti con cache.
"""
import hashlib
import io
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger('generate_image')

CACHE_DIR  = Path(__file__).parent.parent / '.cache' / 'images'
REPO_ROOT  = Path(__file__).parent.parent
VALID_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


# ── Fetch immagine ─────────────────────────────────────────────────────────────

def _is_safe_url(url: str) -> bool:
    """Verifica che l'URL sia HTTPS e non contenga redirect/path sospetti."""
    return bool(url) and url.startswith('https://') and '..' not in url


def _cache_path_for_url(url: str) -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    # Determina l'estensione dall'URL (fallback .jpg)
    ext = Path(url.split('?')[0]).suffix.lower()
    if ext not in VALID_EXTS:
        ext = '.jpg'
    return CACHE_DIR / f'{h}{ext}'


def _download(url: str) -> 'Image':
    """Scarica immagine da URL HTTPS → PIL.Image RGB (EXIF-corretto)."""
    import requests
    from PIL import Image, ImageFile, ImageOps
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    logger.info(f'    Downloading image...')
    r = requests.get(url, timeout=20, allow_redirects=True,
                     headers={'User-Agent': 'DDGFFSite/1.0'})
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content))
    frame_count = getattr(img, 'n_frames', 1) or 1
    if bool(getattr(img, 'is_animated', False) or frame_count > 1):
        img.seek(frame_count - 1)
        img.load()
        img = img.copy()
    img = ImageOps.exif_transpose(img)  # corregge rotazione EXIF (foto smartphone)
    return img.convert('RGB')


def fetch_source_image(image_source: str) -> 'Image | None':
    """
    Carica l'immagine da:
    - URL HTTPS remoto (con cache)
    - Percorso file locale (assoluto o relativo alla root del repo)
    """
    from PIL import Image

    if not image_source:
        logger.warning('    raw: image_source vuoto')
        return None

    # ── URL remoto ─────────────────────────────────────────────────────────────
    if image_source.startswith('http'):
        if not _is_safe_url(image_source):
            logger.warning(f'    raw: URL non sicuro o non HTTPS: {image_source}')
            return None
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached = _cache_path_for_url(image_source)
        if cached.exists():
            logger.info(f'    Cached image: {cached.name}')
            return Image.open(cached).convert('RGB')
        try:
            img = _download(image_source)
            img.save(str(cached), quality=95)
            logger.info(f'    Cached image: {cached.name}')
            return img
        except Exception as e:
            logger.warning(f'    raw: download fallito: {e}')
            return None

    # ── File locale ────────────────────────────────────────────────────────────
    path = Path(image_source)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        logger.warning(f'    raw: file non trovato: {path}')
        return None
    if path.suffix.lower() not in VALID_EXTS:
        logger.warning(f'    raw: formato non supportato: {path.suffix}')
        return None
    # Sicurezza: path traversal
    try:
        path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        logger.warning(f'    raw: path fuori dalla directory del progetto — bloccato')
        return None
    try:
        from PIL import Image, ImageFile, ImageOps
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        img = Image.open(path)
        frame_count = getattr(img, 'n_frames', 1) or 1
        if bool(getattr(img, 'is_animated', False) or frame_count > 1):
            img.seek(frame_count - 1)
            img.load()
            img = img.copy()
        img = ImageOps.exif_transpose(img)  # corregge rotazione EXIF
        logger.info(f'    Loaded local image: {path.name}')
        return img.convert('RGB')
    except Exception as e:
        logger.warning(f'    raw: errore apertura file: {e}')
        return None


# ── Crop & Resize ──────────────────────────────────────────────────────────────

def smart_crop(img: 'Image', target_w: int, target_h: int) -> 'Image':
    """Delegato a smart_crop module con upper-middle bias."""
    from scripts.smart_crop import smart_vertical_crop
    return smart_vertical_crop(img, target_w, target_h)


# ── OG opzionale con branding minimale ────────────────────────────────────────

def _og_with_minimal_branding(img: 'Image', ded: dict, fonts: dict) -> 'Image':
    """
    Aggiunge un branding MINIMALE all'immagine OG:
    - barra scura trasparente in basso
    - titolo + artista piccoli
    Usato solo se RAW_OG_MODE != 'clean' (default: con branding).
    """
    from PIL import Image, ImageDraw, ImageFont
    result = img.copy().convert('RGBA')
    W, H = result.size

    # Barra scura bottom 15%
    bar_h = int(H * 0.18)
    bar = Image.new('RGBA', (W, bar_h), (0, 0, 0, 180))
    result.paste(bar, (0, H - bar_h), bar)

    draw = ImageDraw.Draw(result)

    def get_font(style: str, size: int):
        from PIL import ImageFont
        path = fonts.get(style) if fonts else None
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    song = ded.get('song_title', '')
    artist = ded.get('artist', '')
    site = os.environ.get('SITE_NAME', 'DDG FF')

    f_title  = get_font('bold', 36)
    f_artist = get_font('regular', 26)
    f_site   = get_font('regular', 18)

    y_base = H - bar_h + 14
    draw.text((W // 2, y_base + 6),  song,   font=f_title,  fill=(255, 255, 255, 230), anchor='mm')
    draw.text((W // 2, y_base + 40), artist, font=f_artist, fill=(200, 180, 240, 200), anchor='mm')
    draw.text((W - 30, H - 16),      site,   font=f_site,   fill=(160, 140, 200, 150), anchor='rm')

    return result.convert('RGB')


# ── Pipeline principale raw ────────────────────────────────────────────────────

def process_raw(ded: dict, fonts: dict,
                vertical_path: 'Path', og_path: 'Path') -> bool:
    """
    Pipeline completa image_mode=raw:
    - Portrait source: smart crop 1080x1350 + smart OG crop (upper-middle bias)
    - Landscape source: resize preservando ratio + smart OG crop
    - Nessun overlay, nessun testo.
    """
    from PIL import Image
    from scripts.smart_crop import is_landscape, smart_vertical_crop, smart_og_crop

    image_obj = ded.get('image', {})
    if isinstance(image_obj, dict):
        image_source = image_obj.get('source', ded.get('image_source', ''))
    else:
        image_source = ded.get('image_source', '')

    source_type = 'remote URL' if image_source.startswith('http') else 'local file'
    logger.info(f'    Source type: {source_type}')

    img = fetch_source_image(image_source)
    if img is None:
        logger.warning('    raw: immagine non disponibile — uso fallback locale')
        return False

    try:
        landscape = is_landscape(img)
        if landscape:
            logger.info('    Landscape image detected — landscape pan mode enabled')
            logger.info('    Full image preserved (no portrait crop)')
            # Ridimensiona mantenendo il ratio (max 1200px wide)
            max_w = 1200
            scale = min(1.0, max_w / img.width)
            new_w = int(img.width * scale)
            new_h = int(img.height * scale)
            v = img.resize((new_w, new_h), Image.LANCZOS)
        else:
            logger.info('    Portrait image detected')
            logger.info('    Applying smart portrait crop')
            v = smart_vertical_crop(img, 1080, 1350)

        logger.info('    Generating vertical WebP...')
        v.save(str(vertical_path), 'WEBP', quality=92)
        logger.info(f'    ✓ {vertical_path.name}')

        # OpenGraph — sempre smart_og_crop
        logger.info('    Generating OpenGraph WebP...')
        og_base = smart_og_crop(img, 1200, 630)

        raw_og_mode = os.environ.get('RAW_OG_MODE', 'branded').strip().lower()
        if raw_og_mode == 'clean':
            og_final = og_base
        else:
            og_final = _og_with_minimal_branding(og_base, ded, fonts)
        og_final.save(str(og_path), 'WEBP', quality=92)
        logger.info(f'    ✓ {og_path.name}')
        logger.info('    Completed successfully')
        return True

    except Exception as e:
        logger.error(f'    raw: errore salvataggio: {e}')
        return False
