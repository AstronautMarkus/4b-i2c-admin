from datetime import date, datetime
from time import sleep

from core.http_utils import get_json
from core.module_base import BaseModule

STAR_CHAR = 0
STAR_BITMAP = [
    0b00100, 0b00100, 0b10101, 0b01110,
    0b11111, 0b01110, 0b10101, 0b00100,
]


def get_holidays(year):
    """
    List of Chilean holidays for 'year' via boostr.cl (free, no API key).
    Docs: https://boostr.cl/feriados
    Each item: {"date": "YYYY-MM-DD", "title": ..., "type": ..., "inalienable": bool}
    """
    data = get_json(f"https://api.boostr.cl/holidays/{year}.json")
    if not data or data.get("status") != "success":
        return None
    return data.get("data", [])


def find_holiday_on(holidays, date_str):
    return next((h for h in holidays if h.get("date") == date_str), None)


def find_next_holiday(holidays, date_str):
    upcoming = sorted((h for h in holidays if h.get("date") > date_str), key=lambda h: h["date"])
    return upcoming[0] if upcoming else None


class Module(BaseModule):
    def setup(self, ctx):
        ctx.display.create_char(STAR_CHAR, STAR_BITMAP)

    def tick(self, ctx):
        cache = ctx.cache
        year = datetime.now().year
        if cache.get("holidays_year") != year:
            cache["holidays"] = get_holidays(year)
            cache["holidays_year"] = year

        holidays = cache.get("holidays")
        if not holidays:
            return "Holidays CL:", "no connection"

        today = date.today()
        today_str = today.isoformat()

        today_holiday = find_holiday_on(holidays, today_str)
        if today_holiday:
            self._celebrate(ctx.display, today_holiday["title"])
            return None

        next_holiday = find_next_holiday(holidays, today_str)
        if next_holiday:
            days_left = (date.fromisoformat(next_holiday["date"]) - today).days
            return next_holiday["title"][:16], f"In {days_left} days"
        return "Holidays CL:", "none left"

    def _celebrate(self, display, title):
        """
        Celebration animation for when TODAY is a holiday: the title
        flashes between stars and the holiday name scrolls across the
        second line flanked by a custom star character (CGRAM).
        """
        display.clear()
        for _ in range(4):
            display.write_lines("*" * 16, "")
            sleep(0.15)
            display.write_lines(" HOLIDAY TODAY! ", "")
            sleep(0.35)

        scrolling = f"  {title}  " * 2
        star = chr(STAR_CHAR)
        for offset in range(len(title) + 4):
            window = scrolling[offset:offset + 14].ljust(14)[:14]
            display.write_lines(" HOLIDAY TODAY! ", star + window + star)
            sleep(0.25)
