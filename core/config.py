import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "dashboard.sqlite3"
MODULES_DIR = BASE_DIR / "modules"

WEB_HOST = "0.0.0.0"
WEB_PORT = 6767

# "auto" | "real" | "console" - ver core/lcd_iface.py
LCD_BACKEND = os.environ.get("LCD_BACKEND", "auto")

WAITING_POLL_SECONDS = 2
HTTP_TIMEOUT = 5
WEATHER_CACHE_SECONDS = 900
