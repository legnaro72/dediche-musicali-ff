"""
publish_daily.py - Pubblica la dedica del giorno.

Legge i JSON locali, trova la dedica del giorno, la valida, genera
l'immagine, aggiorna solo il JSON della data target e prepara today.json.

Uso:
    python scripts/publish_daily.py
    python scripts/publish_daily.py --date 2026-05-12
    python scripts/publish_daily.py --date 2026-05-12 --force-republish
    python scripts/publish_daily.py --date 2026-05-12 --dry-run
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils import (
    setup_logging, get_rome_today, save_json,
    get_dedication_storage_path, load_all_dedications, load_dedications_for_date,
    get_dedication_storage_id, get_rome_now,
)

logger = setup_logging('publish')


def set_github_output(name: str, value: str) -> None:
    """Scrive un output GitHub Actions quando lo script gira in workflow."""
    output_path = os.environ.get('GITHUB_OUTPUT')
    if not output_path:
        return
    with open(output_path, 'a', encoding='utf-8') as output_file:
        output_file.write(f"{name}={value}\n")


def find_todays_dedications(date_str: str, target_id: str = None):
    """Cerca tutte le dediche per la data indicata."""
    dedications = load_dedications_for_date(date_str, statuses=('scheduled', 'published'))
    if target_id:
        dedications = [d for d in dedications if d.get('id') == target_id]
    return dedications


def find_latest_published():
    """Trova l'ultima dedica pubblicata (per fallback homepage)."""
    today = get_rome_today()
    candidates = []
    for ded in load_all_dedications():
        if ded.get('status') == 'published' and ded.get('date', '') <= today:
            candidates.append(ded)
    if not candidates:
        return None
    return sorted(candidates, key=lambda d: d.get('date', ''))[-1]


def log_untouched_archive(target_date: str) -> None:
    """Logga esplicitamente che le altre dediche restano in archivio."""
    untouched = [
        get_dedication_storage_path(d).name
        for d in load_all_dedications()
        if d.get('date') != target_date
    ]
    for file_name in sorted(untouched):
        logger.info(f"  File non toccato: {file_name}")
    logger.info("Nessun file eliminato: pubblicazione append-only.")


def normalize_asset_paths(ded: dict) -> dict:
    """Usa id come nome stabile delle immagini finali."""
    storage_id = get_dedication_storage_id(ded)
    image = ded.setdefault('image', {})
    if isinstance(image, dict) and storage_id:
        image['path'] = f'/images/dedications/{storage_id}.webp'
    return ded


def mark_as_published(ded: dict, dry_run: bool = False) -> bool:
    """Aggiorna lo status a 'published' e updated_at solo per la data target."""
    ded = normalize_asset_paths(ded)
    ded['status'] = 'published'
    ded['updated_at'] = get_rome_now().isoformat()

    if dry_run:
        logger.info(f"  [DRY RUN] Aggiornerebbe status -> published: {ded['id']}")
        return True

    path = get_dedication_storage_path(ded)
    existed = path.exists()
    ok = save_json(ded, path)
    if ok:
        if existed:
            logger.info(f"  File aggiornato: {path.name}")
        else:
            logger.info(f"  File creato: {path.name}")
    return ok


def write_today_json(ded: dict, dry_run: bool = False) -> bool:
    """Scrive il file today.json per il frontend."""
    from scripts.utils import ROOT_DIR
    today_path = ROOT_DIR / 'data' / 'today.json'

    if dry_run:
        logger.info("  [DRY RUN] Scriverebbe data/today.json")
        return True

    return save_json(ded, today_path)


def publish(date_str: str, force_republish: bool = False, dry_run: bool = False,
            target_id: str = None) -> bool:
    set_github_output('published', 'false')
    logger.info(f"Data target: {date_str} (Europe/Rome)")
    if target_id:
        logger.info(f"ID target: {target_id}")

    dedications = find_todays_dedications(date_str, target_id=target_id)
    if not dedications:
        logger.warning(f"Nessuna dedica trovata per {date_str}. Il sito resta invariato.")
        log_untouched_archive(date_str)
        return True

    logger.info(f"Trovate {len(dedications)} dediche per {date_str}")
    from scripts.generate_image import ensure_fonts, generate_for_dedication
    from scripts.validate_dedications import validate_dedication
    fonts = ensure_fonts()

    published = []
    changed = False
    for ded in dedications:
        ded_id = ded.get('id', '?')
        logger.info(f"Trovata: {ded_id} [{ded.get('status')}]")

        if ded.get('status') == 'published' and not force_republish:
            logger.info(f"Dedica {ded_id} gia' pubblicata. Usa --force-republish per forzare.")
            logger.info(f"  File non toccato: {get_dedication_storage_path(ded).name}")
            published.append(ded)
            continue

        errors = validate_dedication(ded, set(), {})
        if errors:
            logger.error(f"Validazione fallita per {ded_id}:")
            for e in errors:
                logger.error(f"   - {e}")
            return False

        logger.info(f"Generazione immagine per {ded_id}...")
        img_ok = generate_for_dedication(ded, fonts, dry_run=dry_run)
        if not img_ok:
            logger.error(f"Generazione immagine fallita per {ded_id}")
            return False

        if not mark_as_published(ded, dry_run):
            logger.error(f"Impossibile aggiornare stato dedica {ded_id}")
            return False
        published.append(ded)
        changed = True

    if not changed:
        logger.info("Nessuna nuova dedica pubblicata: build, deploy ed email non necessari.")
        log_untouched_archive(date_str)
        return True

    primary = sorted(published, key=lambda d: (str(d.get('daily_order', '')), d.get('id', '')))[0]
    if not write_today_json(primary, dry_run):
        logger.error("Impossibile scrivere today.json")
        return False

    set_github_output('published', 'true')
    log_untouched_archive(date_str)
    logger.info(f"Pubblicate/aggiornate {len(published)} dediche per {date_str}")
    return True


def main():
    parser = argparse.ArgumentParser(description='Pubblica la dedica del giorno')
    parser.add_argument('--date', default=None, help='Data (YYYY-MM-DD), default: oggi Rome')
    parser.add_argument('--id', default=None, help='Pubblica solo questa dedica')
    parser.add_argument('--force-republish', action='store_true', help='Forza ripubblicazione')
    parser.add_argument('--dry-run', action='store_true', help='Simula senza scrivere')
    args = parser.parse_args()

    date_str = args.date or get_rome_today()
    logger.info("=== Pubblicazione giornaliera DDG FF ===")

    ok = publish(
        date_str,
        force_republish=args.force_republish,
        dry_run=args.dry_run,
        target_id=args.id,
    )
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
