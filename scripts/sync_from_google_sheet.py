"""
sync_from_google_sheet.py - Legge le dediche dal Google Sheet DDG FF e genera i JSON.

Richiede:
  GOOGLE_SERVICE_ACCOUNT_JSON  (contenuto JSON del service account)
  GOOGLE_SHEET_ID              (ID del foglio Google DDG FF)

Uso:
    python scripts/sync_from_google_sheet.py
    python scripts/sync_from_google_sheet.py --date 2026-05-13
    python scripts/sync_from_google_sheet.py --date 2026-05-13 --force-republish
"""
import sys
import os
import json
import argparse

# Carica variabili locali da .env solo in sviluppo.
# In produzione GitHub Actions continuera' a usare i Secrets.
try:
    from dotenv import load_dotenv
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(base_dir, ".env"))
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils import (
    setup_logging, save_json, load_json, get_dedication_storage_path,
    get_italian_day_name, auto_seo_title, auto_seo_description,
    auto_image_alt, get_rome_now,
)
from scripts.dedication_feedback import merge_existing_feedback

logger = setup_logging('sync')

REQUIRED_COLUMNS = [
    'id', 'date', 'status', 'song_title', 'artist',
    'dedication_title', 'dedication_text', 'audio_url', 'audio_type',
]

VIDEO_POSTER_PLACEHOLDER = '/images/og-default.png?v=dediche-musicali-ff-video-poster-20260602'
VALID_VIDEO_TYPES = {'youtube', 'mp4', 'external'}


def get_gspread_client():
    """Crea client gspread da variabile d'ambiente o file."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
        ]

        sa_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON', '')
        if sa_json:
            sa_info = json.loads(sa_json)
            creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
        else:
            # Fallback a file locale (sviluppo)
            sa_file = os.path.join(os.path.dirname(__file__), '..', 'service_account.json')
            if not os.path.exists(sa_file):
                raise FileNotFoundError(
                    "Credenziali Google mancanti: configura il secret GitHub "
                    "GOOGLE_SERVICE_ACCOUNT_JSON oppure aggiungi service_account.json "
                    "solo in sviluppo locale."
                )
            creds = Credentials.from_service_account_file(sa_file, scopes=scopes)

        return gspread.authorize(creds)

    except Exception as e:
        logger.error(f"Errore autenticazione Google: {e}")
        raise


def _cell(row: dict, key: str, default: str = '') -> str:
    return str(row.get(key, default)).strip()


def default_dedication_text(song_title: str, artist: str) -> str:
    return (
        "Ci sono canzoni che arrivano senza fare rumore, "
        "ma restano dentro piu' di tante parole.\n"
        f"Oggi ti dedico \"{song_title}\" di {artist}, "
        "perche' certe emozioni meritano di essere ascoltate fino in fondo."
    )


def normalize_audio(row: dict) -> dict:
    """Normalizza il nuovo modello senza richiedere una migrazione delle vecchie righe Spotify."""
    legacy_type = _cell(row, 'audio_type', 'other').lower() or 'other'
    source_type = _cell(row, 'source_type').lower()
    if not source_type:
        source_type = 'spotify' if legacy_type == 'spotify' else 'external_url'
    if source_type not in {'spotify', 'external_url', 'uploaded_audio'}:
        raise ValueError(f"source_type non valido: '{source_type}'")
    return {
        'url': _cell(row, 'audio_url'),
        'type': legacy_type,
        'source_type': source_type,
        'original_filename': _cell(row, 'original_filename'),
        'mime_type': _cell(row, 'mime_type'),
    }


def normalize_video(row: dict) -> dict | None:
    video_type = _cell(row, 'video_type').lower()
    video_url = _cell(row, 'video_url')
    if not video_type and not video_url:
        return None
    if video_type not in VALID_VIDEO_TYPES:
        raise ValueError(
            f"video_type non valido: '{video_type}'. Ammessi: {sorted(VALID_VIDEO_TYPES)}"
        )
    if not video_url:
        raise ValueError(f"video_url obbligatorio quando video_type={video_type}")

    return {
        'type': video_type,
        'url': video_url,
        'poster': _cell(row, 'video_poster') or VIDEO_POSTER_PLACEHOLDER,
        'title': _cell(row, 'video_title'),
        'description': _cell(row, 'video_description'),
    }


def sheet_row_to_dict(row: dict, default_vote_url: str) -> dict:
    """Converte una riga del Google Sheet in un dict dedica normalizzato."""
    date_str = _cell(row, 'date')
    ded_id = _cell(row, 'id')
    tags_raw = _cell(row, 'tags')
    tags = [t.strip() for t in tags_raw.split(',') if t.strip()] if tags_raw else []

    vote_url = _cell(row, 'vote_url') or default_vote_url
    image_mode = _cell(row, 'image_mode', 'auto') or 'auto'

    seo_title = _cell(row, 'seo_title')
    seo_desc = _cell(row, 'seo_description')
    image_alt = _cell(row, 'image_alt')
    song_title = _cell(row, 'song_title')
    artist = _cell(row, 'artist')
    dedication_text = _cell(row, 'dedication_text') or default_dedication_text(song_title, artist)

    now_str = get_rome_now().isoformat()

    dedication = {
        'id': ded_id,
        'date': date_str,
        'day_name': get_italian_day_name(date_str),
        'status': _cell(row, 'status', 'draft'),
        'song_title': song_title,
        'artist': artist,
        'dedication_title': _cell(row, 'dedication_title'),
        'dedication_text': dedication_text,
        'audio': normalize_audio(row),
        'vote': {
            'url': vote_url,
        },
        'image': {
            'path': f'/images/dedications/{ded_id}.webp',
            'alt': image_alt or auto_image_alt({
                'song_title': _cell(row, 'song_title'),
                'artist': _cell(row, 'artist'),
                'date': date_str,
            }),
            'mode': image_mode,
            'source': _cell(row, 'image_source'),
        },
        'short_phrase': _cell(row, 'short_phrase'),
        'tags': tags,
        'seo': {
            'title': seo_title or auto_seo_title({
                'song_title': song_title,
                'artist': artist,
                'date': date_str,
            }),
            'description': seo_desc or auto_seo_description({
                'dedication_text': dedication_text,
            }),
        },
        'created_at': now_str,
        'updated_at': now_str,
    }
    video = normalize_video(row)
    if video:
        dedication['video'] = video
    return dedication


def save_sheet_dedication(row: dict, default_vote_url: str, dry_run: bool = False,
                          force_republish: bool = False) -> str:
    """Salva una riga del foglio rispettando la regola append-only."""
    ded_id = _cell(row, 'id')
    date_str = _cell(row, 'date')
    status = _cell(row, 'status')

    if status == 'disabled':
        logger.info(f"  FILE NON TOCCATO (disabled nel foglio): {date_str}.json [{ded_id}]")
        return 'skipped'

    path = get_dedication_storage_path({'id': ded_id, 'date': date_str})
    existing = load_json(path) if path.exists() else None

    if existing and existing.get('status') == 'published' and not force_republish:
        logger.info(
            f"  FILE NON TOCCATO (gia' published, no force_republish): {path.name} [{ded_id}]"
        )
        return 'skipped'

    ded = sheet_row_to_dict(row, default_vote_url)
    if existing and existing.get('created_at'):
        ded['created_at'] = existing['created_at']
    ded = merge_existing_feedback(ded, existing)

    action = 'updated' if path.exists() else 'created'
    if dry_run:
        label = 'aggiornato' if action == 'updated' else 'creato'
        logger.info(f"  [DRY RUN] File {label}: {path.name}")
        return action

    if not save_json(ded, path):
        logger.error(f"  Errore salvataggio: {ded_id}")
        return 'error'

    if action == 'updated':
        logger.info(f"  File aggiornato: {path.name}")
    else:
        logger.info(f"  File creato: {path.name}")
    return action


def sync_rows(rows: list, default_vote_url: str, dry_run: bool = False,
              target_date: str = None, target_id: str = None,
              force_republish: bool = False) -> bool:
    """Sincronizza righe gia' lette dal Google Sheet senza cancellare file locali."""
    saved = 0
    skipped = 0
    errors = 0
    matched = 0

    for row in rows:
        ded_id = _cell(row, 'id')
        date_str = _cell(row, 'date')

        if not ded_id or not date_str:
            logger.warning(f"Riga senza id o date: {row} - saltata")
            skipped += 1
            continue

        if target_date and date_str != target_date:
            logger.info(f"  FILE NON TOCCATO (fuori data target {target_date}): {date_str}.json [{ded_id}]")
            skipped += 1
            continue

        if target_id and ded_id != target_id:
            logger.info(f"  FILE NON TOCCATO (fuori id target {target_id}): {date_str}.json [{ded_id}]")
            skipped += 1
            continue

        matched += 1

        try:
            result = save_sheet_dedication(
                row,
                default_vote_url,
                dry_run=dry_run,
                force_republish=force_republish,
            )
            if result in ('created', 'updated'):
                saved += 1
            elif result == 'skipped':
                skipped += 1
            else:
                errors += 1
        except Exception as e:
            logger.error(f"  Errore per '{ded_id}': {e}")
            errors += 1

    logger.info("Nessun file eliminato: sync append-only, archivio locale preservato.")
    logger.info(f"\nSync completata: {saved} creati/aggiornati, {skipped} non toccati, {errors} errori")
    if (target_date or target_id) and matched == 0:
        logger.error(
            "Nessuna riga del Google Sheet corrisponde ai filtri richiesti "
            f"(date={target_date or '-'}, id={target_id or '-'})."
        )
        return False
    return errors == 0


def sync(dry_run: bool = False, target_date: str = None, target_id: str = None,
         force_republish: bool = False):
    """Sincronizza dal Google Sheet."""
    sheet_id = os.environ.get('GOOGLE_SHEET_ID', '')
    if not sheet_id:
        logger.error("GOOGLE_SHEET_ID non configurato")
        sys.exit(1)

    default_vote_url = os.environ.get('DEFAULT_VOTE_URL', '')

    logger.info("Connessione a Google Sheets...")
    gc = get_gspread_client()
    sh = gc.open_by_key(sheet_id)
    ws = sh.get_worksheet(0)

    rows = ws.get_all_records()
    logger.info(f"Trovate {len(rows)} righe nel Google Sheet")
    if target_date:
        logger.info(f"Data target sync: {target_date}")
    if target_id:
        logger.info(f"ID target sync: {target_id}")

    return sync_rows(
        rows,
        default_vote_url,
        dry_run=dry_run,
        target_date=target_date,
        target_id=target_id,
        force_republish=force_republish,
    )


def main():
    parser = argparse.ArgumentParser(description='Sync da Google Sheet')
    parser.add_argument('--dry-run', action='store_true', help='Non scrivere file')
    parser.add_argument('--date', default=None, help='Sincronizza solo questa data (YYYY-MM-DD)')
    parser.add_argument('--id', default=None, help='Sincronizza solo questa dedica')
    parser.add_argument('--force-republish', action='store_true',
                        help='Permette di sovrascrivere dediche gia published')
    args = parser.parse_args()

    logger.info("=== Sync da Google Sheet DDG FF ===")
    ok = sync(
        dry_run=args.dry_run,
        target_date=args.date,
        target_id=args.id,
        force_republish=args.force_republish,
    )
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
