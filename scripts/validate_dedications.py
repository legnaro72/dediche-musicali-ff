"""
validate_dedications.py - Valida le dediche prima del deploy.

Uso:
    python scripts/validate_dedications.py
    python scripts/validate_dedications.py --strict
"""
import sys
import os
import re
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils import (
    setup_logging, load_all_dedications, is_valid_url,
    parse_date, VALID_STATUSES, VALID_IMAGE_MODES, VALID_AUDIO_TYPES,
    VALID_VIDEO_TYPES,
)

logger = setup_logging('validate')


def is_youtube_url(url: str) -> bool:
    return bool(re.search(r'(youtube\.com/(watch\?v=|embed/|shorts/)|youtu\.be/)[A-Za-z0-9_-]{11}', url))


def is_mp4_url(url: str) -> bool:
    clean_url = url.split('?', 1)[0].lower()
    return clean_url.endswith('.mp4')


def validate_dedication(ded: dict, seen_ids: set, active_dates: dict = None) -> list:
    """Restituisce una lista di messaggi di errore per la dedica."""
    errors = []
    ded_id = ded.get('id', '').strip()

    if not ded_id:
        errors.append("Campo 'id' mancante")
    elif ded_id in seen_ids:
        errors.append(f"ID duplicato: '{ded_id}'")
    elif not re.match(r'^[a-z0-9\-]+$', ded_id):
        errors.append(f"ID '{ded_id}' non valido (solo lettere minuscole, numeri, trattini)")

    date = ded.get('date', '').strip()
    if not date:
        errors.append("Campo 'date' mancante")
    elif not parse_date(date):
        errors.append(f"Data '{date}' non nel formato YYYY-MM-DD")

    status = ded.get('status', '').strip()
    if not status:
        errors.append("Campo 'status' mancante")
    elif status not in VALID_STATUSES:
        errors.append(f"Status '{status}' non valido. Ammessi: {sorted(VALID_STATUSES)}")

    # Piu' dediche possono condividere la stessa data. L'unicita' resta sull'id.

    for field in ['song_title', 'artist', 'dedication_title', 'dedication_text']:
        if not ded.get(field, '').strip():
            errors.append(f"Campo '{field}' mancante o vuoto")

    audio = ded.get('audio', {})
    audio_url = audio.get('url', '').strip() if isinstance(audio, dict) else ''
    audio_type = audio.get('type', '').strip() if isinstance(audio, dict) else ''
    if not audio_url:
        errors.append("Campo 'audio.url' mancante")
    elif not is_valid_url(audio_url):
        errors.append(f"audio.url non e' un URL https valido: '{audio_url}'")
    if audio_type and audio_type not in VALID_AUDIO_TYPES:
        errors.append(f"audio.type '{audio_type}' non valido. Ammessi: {sorted(VALID_AUDIO_TYPES)}")

    image = ded.get('image', {})
    image_mode = image.get('mode', 'auto').strip() if isinstance(image, dict) else 'auto'
    if image_mode and image_mode not in VALID_IMAGE_MODES:
        errors.append(f"image.mode '{image_mode}' non valido. Ammessi: {sorted(VALID_IMAGE_MODES)}")

    video = ded.get('video', {})
    if isinstance(video, dict) and (video.get('type') or video.get('url')):
        video_type = str(video.get('type', '')).strip()
        video_url = str(video.get('url', '')).strip()
        if not video_type:
            errors.append("video.type mancante")
        elif video_type not in VALID_VIDEO_TYPES:
            errors.append(f"video.type '{video_type}' non valido. Ammessi: {sorted(VALID_VIDEO_TYPES)}")
        if not video_url:
            errors.append("video.url mancante")
        elif not is_valid_url(video_url):
            errors.append(f"video.url non e' un URL https valido: '{video_url}'")
        elif video_type == 'youtube' and not is_youtube_url(video_url):
            errors.append(f"video.url non e' un link YouTube valido: '{video_url}'")
        elif video_type == 'mp4' and not is_mp4_url(video_url):
            errors.append(f"video.url deve puntare a un file .mp4: '{video_url}'")

    vote = ded.get('vote', {})
    vote_url = vote.get('url', '').strip() if isinstance(vote, dict) else ''
    default_vote_url = os.environ.get('DEFAULT_VOTE_URL', '').strip()
    if not vote_url and not default_vote_url:
        errors.append("vote.url vuoto e DEFAULT_VOTE_URL non configurato")
    elif vote_url and not is_valid_url(vote_url):
        errors.append(f"vote.url non e' un URL https valido: '{vote_url}'")

    return errors


def validate_all(dedications: list) -> bool:
    """Valida tutte le dediche. Restituisce True se tutte passano."""
    seen_ids = set()
    total_errors = 0

    for ded in dedications:
        ded_id = ded.get('id', '<NESSUN_ID>')
        status = ded.get('status', '')

        if status == 'draft':
            logger.info(f"  SKIP (draft): {ded_id}")
            continue

        errors = validate_dedication(ded, seen_ids)

        if ded.get('id'):
            seen_ids.add(ded['id'])

        if errors:
            total_errors += len(errors)
            logger.error(f"ERRORI in '{ded_id}':")
            for e in errors:
                logger.error(f"   - {e}")
        else:
            logger.info(f"  OK: {ded_id} [{status}]")

    if total_errors:
        logger.error(f"\nValidazione FALLITA: {total_errors} errori trovati")
        return False

    logger.info(f"\nValidazione OK: {len(dedications)} dediche valide")
    return True


def main():
    parser = argparse.ArgumentParser(description='Valida le dediche DDG FF')
    parser.add_argument('--strict', action='store_true', help='Blocca anche su warning')
    args = parser.parse_args()

    logger.info("=== Validazione dediche DDG FF ===")

    dedications = load_all_dedications()
    logger.info(f"Trovate {len(dedications)} dediche in data/dedications/")

    if not dedications:
        logger.warning("Nessuna dedica trovata.")
        sys.exit(0)

    success = validate_all(dedications)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
