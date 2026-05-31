"""
utils.py — Funzioni condivise per DDG FF.
"""
import json
import os
import re
import logging
from datetime import datetime
from pathlib import Path

import pytz

# ── Costanti ─────────────────────────────────────────────────────────────────
ROME_TZ = pytz.timezone('Europe/Rome')

ROOT_DIR        = Path(__file__).parent.parent
DATA_DIR        = ROOT_DIR / 'data' / 'dedications'
IMAGES_DIR      = ROOT_DIR / 'public' / 'images' / 'dedications'
FONTS_DIR       = ROOT_DIR / 'public' / 'fonts'

VALID_STATUSES    = {'draft', 'scheduled', 'published', 'disabled'}
VALID_IMAGE_MODES = {'auto', 'upload', 'raw', 'none'}
VALID_AUDIO_TYPES = {'spotify', 'youtube', 'soundcloud', 'mp3', 'cloud', 'other'}
VALID_VIDEO_TYPES = {'youtube', 'mp4', 'external'}

ITALIAN_DAYS   = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']
ITALIAN_MONTHS = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
                  'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']


# ── Logging ──────────────────────────────────────────────────────────────────
def setup_logging(name: str = 'ddgff') -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    return logging.getLogger(name)


# ── Date helpers ─────────────────────────────────────────────────────────────
def get_rome_now() -> datetime:
    return datetime.now(ROME_TZ)


def get_rome_today() -> str:
    return get_rome_now().strftime('%Y-%m-%d')


def parse_date(date_str: str):
    try:
        dt = datetime.strptime(date_str.strip(), '%Y-%m-%d')
        return ROME_TZ.localize(dt)
    except (ValueError, AttributeError):
        return None


def get_italian_day_name(date_str: str) -> str:
    dt = parse_date(date_str)
    return ITALIAN_DAYS[dt.weekday()] if dt else ''


def get_italian_month_name(month_num: int) -> str:
    return ITALIAN_MONTHS[month_num - 1] if 1 <= month_num <= 12 else ''


def format_date_italian(date_str: str) -> str:
    dt = parse_date(date_str)
    if dt:
        return f'{dt.day} {get_italian_month_name(dt.month)} {dt.year}'
    return date_str


# ── URL helpers ───────────────────────────────────────────────────────────────
def is_valid_url(url: str) -> bool:
    if not url:
        return False
    return bool(re.match(r'^https://.+', url.strip()))


# ── JSON helpers ─────────────────────────────────────────────────────────────
def load_json(path: Path):
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception:
        return None


def save_json(data: dict, path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_all_dedications() -> list:
    dedications = []
    if not DATA_DIR.exists():
        return dedications
    for json_file in sorted(DATA_DIR.glob('*.json')):
        data = load_json(json_file)
        if data:
            dedications.append(data)
    return dedications


def get_dedication_json_path(identifier: str) -> Path:
    return DATA_DIR / f'{identifier}.json'


def get_dedication_storage_id(ded: dict) -> str:
    """Restituisce l'identificatore stabile usato per nuovi file JSON/immagini."""
    return (ded.get('id') or ded.get('date') or '').strip()


def find_existing_dedication_path(ded_id: str = '', date_str: str = ''):
    """Trova un JSON esistente per id oppure, per compatibilita', per data legacy."""
    if not DATA_DIR.exists():
        return None

    ded_id = (ded_id or '').strip()
    date_str = (date_str or '').strip()

    if ded_id:
        id_path = get_dedication_json_path(ded_id)
        if id_path.exists():
            return id_path

    if date_str:
        legacy_path = get_dedication_json_path(date_str)
        if legacy_path.exists():
            legacy = load_json(legacy_path)
            if legacy and (not ded_id or legacy.get('id') == ded_id):
                return legacy_path

    for json_file in sorted(DATA_DIR.glob('*.json')):
        data = load_json(json_file)
        if not data:
            continue
        if ded_id and data.get('id') == ded_id:
            return json_file
        if date_str and not ded_id and data.get('date') == date_str:
            return json_file
    return None


def get_dedication_storage_path(ded: dict) -> Path:
    """Percorso JSON append-only: legacy se esiste, altrimenti {id}.json."""
    ded_id = (ded.get('id') or '').strip()
    date_str = (ded.get('date') or '').strip()
    existing = find_existing_dedication_path(ded_id, date_str)
    if existing:
        return existing
    storage_id = get_dedication_storage_id(ded)
    return get_dedication_json_path(storage_id)


def load_dedications_for_date(date_str: str, statuses=None) -> list:
    dedications = [d for d in load_all_dedications() if d.get('date') == date_str]
    if statuses is not None:
        dedications = [d for d in dedications if d.get('status') in statuses]
    return sorted(dedications, key=lambda d: (str(d.get('daily_order', '')), d.get('id', '')))


# ── Text helpers ──────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    text = text.lower()
    for src, dst in [('àáâã','a'),('èéêë','e'),('ìíîï','i'),('òóôõö','o'),('ùúûü','u')]:
        for c in src:
            text = text.replace(c, dst)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def auto_seo_title(ded: dict) -> str:
    return f"{ded.get('song_title','')} – {ded.get('artist','')} | {ded.get('date','')}"


def auto_seo_description(ded: dict) -> str:
    text = ded.get('dedication_text', '')
    return text[:155].rstrip() + ('…' if len(text) > 155 else '')


def auto_image_alt(ded: dict) -> str:
    return (f"Dedica musicale: {ded.get('song_title','')} di {ded.get('artist','')} "
            f"del {format_date_italian(ded.get('date',''))}")
