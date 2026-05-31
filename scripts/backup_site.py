"""
backup_site.py — Crea un backup zip del sito.

Uso:
    python scripts/backup_site.py
    python scripts/backup_site.py --output backups/backup-2026-05-12.zip
"""
import sys
import os
import zipfile
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils import setup_logging, get_rome_now, ROOT_DIR

logger = setup_logging('backup')

BACKUP_DIRS = [
    'data',
    'public/images/dedications',
    'src',
    'scripts',
    '.github/workflows',
]

BACKUP_FILES = [
    'package.json',
    'astro.config.mjs',
    'requirements.txt',
    'README.md',
]


def create_backup(output_path: Path) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Creazione backup: {output_path}")

    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Aggiungi directory
            for dir_rel in BACKUP_DIRS:
                dir_abs = ROOT_DIR / dir_rel
                if not dir_abs.exists():
                    logger.warning(f"  Directory non trovata (skip): {dir_rel}")
                    continue
                for file_path in dir_abs.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(ROOT_DIR)
                        zf.write(file_path, arcname)
                        logger.debug(f"  + {arcname}")

            # Aggiungi file singoli
            for file_rel in BACKUP_FILES:
                file_abs = ROOT_DIR / file_rel
                if file_abs.exists():
                    zf.write(file_abs, file_rel)
                    logger.debug(f"  + {file_rel}")

        size_kb = output_path.stat().st_size // 1024
        logger.info(f"✅ Backup creato: {output_path} ({size_kb} KB)")
        return True

    except Exception as e:
        logger.error(f"❌ Errore backup: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Crea backup DDG FF')
    parser.add_argument('--output', default=None, help='Percorso output zip')
    args = parser.parse_args()

    logger.info("=== Backup DDG FF ===")

    today = get_rome_now().strftime('%Y-%m-%d')
    output = Path(args.output) if args.output else ROOT_DIR / 'backups' / f'backup-{today}.zip'

    ok = create_backup(output)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
