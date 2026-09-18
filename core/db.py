import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from core.config import DATA_DIR, DB_PATH

_WRITE_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS modules (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    version TEXT,
    author TEXT,
    icon TEXT,
    tick_seconds REAL NOT NULL DEFAULT 1,
    requires_internet INTEGER NOT NULL DEFAULT 0,
    is_valid INTEGER NOT NULL DEFAULT 1,
    error_message TEXT,
    discovered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS playlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id TEXT NOT NULL REFERENCES modules(id),
    position INTEGER NOT NULL,
    duration_seconds INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

DEFAULT_SETTINGS = {
    "state": "waiting",
    "config_version": "0",
    "published_at": "",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def write_transaction():
    """Serializa escrituras compuestas y las hace atómicas (commit/rollback)."""
    with _WRITE_LOCK, _connect() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with write_transaction() as conn:
        conn.executescript(SCHEMA)
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value)
            )


def query_all(sql, params=()):
    with _connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def query_one(sql, params=()):
    with _connect() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


# --------------------------------------------------------------------------- #
# modules
# --------------------------------------------------------------------------- #

def upsert_module(slug, manifest, is_valid, error_message=None):
    with write_transaction() as conn:
        conn.execute(
            """
            INSERT INTO modules (id, title, description, version, author, icon,
                                  tick_seconds, requires_internet, is_valid, error_message, discovered_at)
            VALUES (:id, :title, :description, :version, :author, :icon,
                    :tick_seconds, :requires_internet, :is_valid, :error_message, :discovered_at)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, description=excluded.description, version=excluded.version,
                author=excluded.author, icon=excluded.icon, tick_seconds=excluded.tick_seconds,
                requires_internet=excluded.requires_internet, is_valid=excluded.is_valid,
                error_message=excluded.error_message, discovered_at=excluded.discovered_at
            """,
            {
                "id": slug,
                "title": manifest.get("title", slug),
                "description": manifest.get("description", ""),
                "version": manifest.get("version", ""),
                "author": manifest.get("author", ""),
                "icon": manifest.get("icon", ""),
                "tick_seconds": manifest.get("tick_seconds", 1),
                "requires_internet": int(bool(manifest.get("requires_internet", False))),
                "is_valid": int(bool(is_valid)),
                "error_message": error_message,
                "discovered_at": _now(),
            },
        )


def mark_missing_as_invalid(found_slugs):
    with write_transaction() as conn:
        rows = conn.execute("SELECT id FROM modules").fetchall()
        for row in rows:
            if row["id"] not in found_slugs:
                conn.execute(
                    "UPDATE modules SET is_valid=0, error_message=? WHERE id=?",
                    ("Módulo no encontrado en disco", row["id"]),
                )


def mark_module_invalid(slug, message):
    with write_transaction() as conn:
        conn.execute(
            "UPDATE modules SET is_valid=0, error_message=? WHERE id=?", (message, slug)
        )


def list_modules():
    return query_all("SELECT * FROM modules ORDER BY title")


def get_module(slug):
    return query_one("SELECT * FROM modules WHERE id=?", (slug,))


# --------------------------------------------------------------------------- #
# playlist
# --------------------------------------------------------------------------- #

def get_active_playlist():
    """Playlist activa (enabled=1) con los datos del módulo ya unidos, en orden."""
    return query_all(
        """
        SELECT p.id, p.module_id, p.position, p.duration_seconds, p.enabled,
               m.title, m.icon, m.is_valid, m.error_message, m.tick_seconds
        FROM playlist p
        JOIN modules m ON m.id = p.module_id
        WHERE p.enabled = 1
        ORDER BY p.position ASC
        """
    )


def replace_playlist(entries):
    """entries: lista de (module_id, duration_seconds) en el orden deseado. Atómico."""
    with write_transaction() as conn:
        conn.execute("DELETE FROM playlist")
        for position, (module_id, duration_seconds) in enumerate(entries):
            conn.execute(
                "INSERT INTO playlist (module_id, position, duration_seconds, enabled) "
                "VALUES (?, ?, ?, 1)",
                (module_id, position, duration_seconds),
            )
        _bump_config_version(conn)
        conn.execute(
            "UPDATE settings SET value=? WHERE key='state'",
            ("running" if entries else "waiting",),
        )
        conn.execute(
            "UPDATE settings SET value=? WHERE key='published_at'", (_now(),)
        )


def factory_reset():
    with write_transaction() as conn:
        conn.execute("DELETE FROM playlist")
        conn.execute("UPDATE settings SET value='waiting' WHERE key='state'")
        conn.execute("UPDATE settings SET value='' WHERE key='published_at'")
        _bump_config_version(conn)


# --------------------------------------------------------------------------- #
# settings
# --------------------------------------------------------------------------- #

def get_setting(key, default=None):
    row = query_one("SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else default


def set_setting(key, value):
    with write_transaction() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_config_version():
    return get_setting("config_version", "0")


def _bump_config_version(conn):
    row = conn.execute("SELECT value FROM settings WHERE key='config_version'").fetchone()
    current = int(row["value"]) if row and row["value"] else 0
    conn.execute(
        "UPDATE settings SET value=? WHERE key='config_version'", (str(current + 1),)
    )
