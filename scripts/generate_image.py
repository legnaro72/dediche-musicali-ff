"""
generate_image.py — Pipeline premium di generazione immagini DDG FF.

Genera:
  - 1080x1350 px  (verticale, social/mobile)
  - 1200x630  px  (OpenGraph)

Uso:
    python scripts/generate_image.py --date 2026-05-12
    python scripts/generate_image.py --date 2026-05-12 --provider local
    python scripts/generate_image.py --date 2026-05-12 --provider openverse
    python scripts/generate_image.py --date 2026-05-12 --provider gemini
    python scripts/generate_image.py --all

Providers (auto-order): gemini → pexels → unsplash → openverse → wikimedia → local
"""
import sys
import os
import argparse
from pathlib import Path

# Carica variabili locali da .env solo in sviluppo.
# In produzione GitHub Actions continuerà a usare i Secrets.
try:
    from dotenv import load_dotenv
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(base_dir, ".env"))
except Exception:
    pass


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils import (
    setup_logging, load_all_dedications, load_json,
    get_dedication_json_path, get_italian_day_name, format_date_italian,
    get_dedication_storage_id, load_dedications_for_date,
    IMAGES_DIR,
)
from scripts.mood_engine import (
    detect_mood, generate_search_query, generate_gemini_prompt, MOOD_PALETTE,
)
from scripts.image_providers import fetch_background, enhance_keywords_with_gemini
from scripts.image_attribution import save_attribution
from scripts.premium_template import (
    ensure_fonts, apply_premium_template_vertical, apply_premium_template_og,
)
from scripts.raw_image_handler import process_raw

logger = setup_logging('generate_image')


def _enrich_ded(ded: dict) -> dict:
    """Aggiunge campi data italiani alla dedica per il template."""
    date_str = ded.get('date', '')
    ded['day_name'] = get_italian_day_name(date_str)
    ded['date_it'] = format_date_italian(date_str)
    return ded


def generate_for_dedication(ded: dict, fonts: dict,
                             provider_override: str = 'auto',
                             dry_run: bool = False) -> bool:
    """
    Genera le immagini per una dedica.
    Segue l'ordine: Gemini → Pexels → Unsplash → Openverse → Wikimedia → local.
    Non blocca mai la pubblicazione.
    """
    date_str = ded.get('date', '')
    if not date_str:
        logger.error('  Dedica senza data')
        return False
    storage_id = get_dedication_storage_id(ded)
    if not storage_id:
        logger.error('  Dedica senza id')
        return False

    # Recupera image_mode (supporta struttura piatta e annidata)
    image_obj = ded.get('image', {})
    if isinstance(image_obj, dict):
        image_mode   = image_obj.get('mode', ded.get('image_mode', 'auto'))
        image_source = image_obj.get('source', ded.get('image_source', ''))
    else:
        image_mode   = ded.get('image_mode', 'auto')
        image_source = ded.get('image_source', '')

    logger.info(f'  Image mode: {image_mode}')

    if image_mode == 'none':
        logger.info('  SKIP (image_mode=none)')
        return True

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    vertical_path = IMAGES_DIR / f'{storage_id}.webp'
    og_path       = IMAGES_DIR / f'{storage_id}-og.webp'
    if isinstance(image_obj, dict):
        image_obj['path'] = f'/images/dedications/{storage_id}.webp'

    if dry_run:
        logger.info(f'  [DRY RUN] Genererebbe: {vertical_path.name}, {og_path.name}')
        return True

    ded = _enrich_ded(ded)

    # ── image_mode = raw ─────────────────────────────────────────────────────
    if image_mode == 'raw':
        logger.info('  Image mode: raw (nessun overlay, solo crop+resize+WebP)')
        ok = process_raw(ded, fonts, vertical_path, og_path)
        if ok:
            return True
        logger.warning('  raw: fallback a modalità auto...')
        image_mode = 'auto'  # prosegue con auto come fallback

    # ── image_mode = upload ──────────────────────────────────────────────────
    if image_mode == 'upload' and image_source:
        src = Path(image_source)
        if src.exists():
            from PIL import Image, ImageOps
            img_raw = Image.open(src)
            bg = ImageOps.exif_transpose(img_raw).convert('RGB')
            logger.info(f'  Uso immagine manuale: {src.name}')
        else:
            logger.warning(f'  image_source non trovato: {src} — uso fallback locale')
            bg = None
        mood = detect_mood(
            ded.get('song_title', ''), ded.get('dedication_text', ''),
            ded.get('short_phrase', ''), str(ded.get('tags', ''))
        )
        palette = MOOD_PALETTE.get(mood, MOOD_PALETTE['default'])
        return _save_images(bg, ded, fonts, palette, vertical_path, og_path,
                            storage_id, attribution=None)

    # ── image_mode = auto ────────────────────────────────────────────────────
    song_title    = ded.get('song_title', '')
    artist        = ded.get('artist', '')
    ded_text      = ded.get('dedication_text', '')
    short_phrase  = ded.get('short_phrase', '')
    tags          = str(ded.get('tags', ''))

    logger.info(f'  Song: {song_title} — {artist}')

    mood    = detect_mood(song_title, ded_text, short_phrase, tags)
    palette = MOOD_PALETTE.get(mood, MOOD_PALETTE['default'])
    logger.info(f'  Mood rilevato: {mood}')

    query  = generate_search_query(song_title, ded_text, short_phrase, tags)
    prompt = generate_gemini_prompt(song_title, artist, ded_text, short_phrase, tags)

    # Prova a migliorare la query con Gemini text (GRATUITO) se disponibile
    enhanced = enhance_keywords_with_gemini(song_title, artist, ded_text, tags)
    if enhanced:
        query = enhanced

    logger.info(f'  Query visiva: {query}')

    eff_provider = provider_override or os.environ.get('IMAGE_PROVIDER', 'auto')
    bg, attribution = fetch_background(prompt, query, eff_provider)

    return _save_images(bg, ded, fonts, palette, vertical_path, og_path,
                        storage_id, attribution)


def _save_images(bg, ded, fonts, palette,
                 vertical_path, og_path, date_str, attribution) -> bool:
    try:
        logger.info('  Applico template premium...')
        v_img = apply_premium_template_vertical(bg, ded, fonts, palette)
        v_img.save(str(vertical_path), 'WEBP', quality=90)
        logger.info(f'  ✓ {vertical_path.name}')

        og_img = apply_premium_template_og(bg, ded, fonts, palette)
        og_img.save(str(og_path), 'WEBP', quality=90)
        logger.info(f'  ✓ {og_path.name}')

        if attribution:
            save_attribution(date_str, attribution)
        return True
    except Exception as e:
        logger.error(f'  ✗ Errore generazione immagini: {e}')
        # Ultimo tentativo: fallback locale puro
        try:
            logger.info('  Tentativo fallback locale di emergenza...')
            from scripts.mood_engine import MOOD_PALETTE
            palette_fb = MOOD_PALETTE['default']
            v_img = apply_premium_template_vertical(None, ded, fonts, palette_fb)
            v_img.save(str(vertical_path), 'WEBP', quality=90)
            og_img = apply_premium_template_og(None, ded, fonts, palette_fb)
            og_img.save(str(og_path), 'WEBP', quality=90)
            logger.info('  ✓ Fallback locale generato')
            return True
        except Exception as e2:
            logger.error(f'  ✗ Fallback locale fallito: {e2}')
            return False


def main():
    parser = argparse.ArgumentParser(description='Genera immagini premium DDG FF')
    parser.add_argument('--date', help='Data specifica (YYYY-MM-DD) oppure id dedica')
    parser.add_argument('--all', action='store_true',
                        help='Genera per tutte le dediche scheduled/published')
    parser.add_argument('--provider', default='auto',
                        choices=['auto', 'gemini', 'pexels', 'unsplash',
                                 'openverse', 'wikimedia', 'local'],
                        help='Forza un provider specifico')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simula senza scrivere file')
    args = parser.parse_args()

    logger.info('=== Generazione immagini DDG FF ===')
    fonts = ensure_fonts()

    if args.date:
        path = get_dedication_json_path(args.date)
        ded = load_json(path)
        dedications = [ded] if ded else load_dedications_for_date(
            args.date,
            statuses=('scheduled', 'published'),
        )
        if not dedications:
            logger.error(f'Dedica non trovata: {args.date}')
            logger.error(f'Cercata anche in: {path}')
            sys.exit(1)
        errors = 0
        for ded in dedications:
            if not generate_for_dedication(ded, fonts,
                                           provider_override=args.provider,
                                           dry_run=args.dry_run):
                errors += 1
        sys.exit(0 if errors == 0 else 1)

    elif args.all:
        dedications = load_all_dedications()
        errors = 0
        for ded in dedications:
            if ded.get('status') in ('published', 'scheduled'):
                if not generate_for_dedication(ded, fonts,
                                               provider_override=args.provider,
                                               dry_run=args.dry_run):
                    errors += 1
        sys.exit(0 if errors == 0 else 1)

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == '__main__':
    main()
