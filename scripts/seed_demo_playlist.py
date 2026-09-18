"""
Puebla la playlist con los 5 módulos migrados, usando las mismas duraciones
que tenía dashboard.py, para poder validar el núcleo sin esperar a la UI web.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import db, scanner  # noqa: E402

DEMO_ENTRIES = [
    ("clock", 6),
    ("network", 5),
    ("hardware", 8),
    ("weather", 5),
    ("holidays", 5),
]


def main():
    db.init_db()
    scanner.discover_modules()

    missing = [slug for slug, _ in DEMO_ENTRIES if db.get_module(slug) is None]
    if missing:
        raise SystemExit(f"Módulos no encontrados tras escanear: {missing}")

    db.replace_playlist(DEMO_ENTRIES)
    print(f"Playlist publicada con {len(DEMO_ENTRIES)} entradas.")


if __name__ == "__main__":
    main()
