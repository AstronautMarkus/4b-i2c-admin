"""
Dashboard for a 16x2 I2C LCD on a Raspberry Pi 4B.

Automatically rotates between several "screens", each with its own
loading indicator while the underlying query resolves:

    - Clock / date        (updates live, every second)
    - Network              (hostname + real private IP of the interface)
    - Hardware             (CPU %, RAM %, disk % and temperature, live)
    - Weather               (IP-based geolocation + Open-Meteo)
    - Chile holidays        (boostr.cl) - celebrates if TODAY is a holiday

This is the "base": simple logic that's easy to extend with more
screens (add an entry to SCREENS + its screen_xxx() function).

--- Requirements ---

System:
    sudo apt install lm-sensors
    sudo sensors-detect          # answer "yes"/enter to the default prompts

Python:
    pip3 install requests psutil
    (or: sudo apt install python3-requests python3-psutil)

Internet connection: required for weather, geolocation and holidays.
If there is no internet, those screens show a notice instead of failing.
"""

import re
import socket
import subprocess
from datetime import date, datetime
from time import sleep

import psutil
import requests

from lcd_i2c import (
    lcd_init,
    lcd_clear,
    lcd_byte,
    lcd_message,
    lcd_create_char,
    lcd_write_at,
    LCD_CMD,
    LCD_LINE_1,
    LCD_LINE_2,
)

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

TICK_SECONDS = 1             # how often "live" data refreshes (clock, hardware)

CLOCK_SECONDS = 6            # how long each screen stays up before the next one
NETWORK_SECONDS = 5
HARDWARE_SECONDS = 8
WEATHER_SECONDS = 5
HOLIDAYS_SECONDS = 5          # duration of the "next holiday" screen (if today is not one)

WEATHER_REFRESH_EVERY = 5    # how many full cycles between weather refreshes

HTTP_TIMEOUT = 5             # max seconds to wait for an HTTP request

SCREENS = ["clock", "network", "hardware", "weather", "holidays"]

SPINNER_FRAMES = ["|", "/", "-", "\\"]

STAR_CHAR = 0
STAR_BITMAP = [
    0b00100, 0b00100, 0b10101, 0b01110,
    0b11111, 0b01110, 0b10101, 0b00100,
]

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Fog",
    51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Showers", 81: "Showers", 82: "Heavy showers",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm",
}


# --------------------------------------------------------------------------- #
# Loading screen
# --------------------------------------------------------------------------- #

def lcd_loading(title, seconds=1.0):
    """Shows a spinner while a slow query (HTTP, sensors...) resolves."""
    lcd_clear()
    lcd_message(title[:16], LCD_LINE_1)
    ticks = max(1, int(seconds / 0.15))
    for i in range(ticks):
        frame = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
        lcd_message(f"Loading... {frame}", LCD_LINE_2)
        sleep(0.15)


# --------------------------------------------------------------------------- #
# Hardware (lm-sensors + psutil)
# --------------------------------------------------------------------------- #

def get_cpu_temp():
    """
    CPU temperature read via lm-sensors (parseable format: `sensors -u`).
    Returns None if lm-sensors is not installed or reports no temperature.
    """
    try:
        output = subprocess.run(
            ["sensors", "-u"], capture_output=True, text=True, timeout=3
        ).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    match = re.search(r"temp\d*_input:\s*([\d.\-]+)", output)
    return float(match.group(1)) if match else None


# --------------------------------------------------------------------------- #
# Network
# --------------------------------------------------------------------------- #

def get_local_ip():
    """
    Real private IP of the active interface (Wi-Fi or Ethernet).

    socket.gethostbyname(hostname) does NOT work on Raspbian: by default
    /etc/hosts maps the hostname to 127.0.1.1, so it always returns
    loopback. This trick opens a UDP socket "towards" a public IP
    without sending any data: it just forces the OS to pick the real
    outbound interface, and we read the local IP assigned to it.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "no network"
    finally:
        s.close()


# --------------------------------------------------------------------------- #
# HTTP: geolocation + weather
# --------------------------------------------------------------------------- #

def get_location():
    """Approximate geolocation by public IP (no API key, no setup required)."""
    try:
        r = requests.get("https://ipwho.is/", timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if not data.get("success", False):
            return None
        return {
            "city": data.get("city", "?"),
            "lat": data.get("latitude"),
            "lon": data.get("longitude"),
        }
    except (requests.RequestException, ValueError):
        return None


def get_weather(lat, lon):
    """Current weather via Open-Meteo (free, no API key)."""
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        current = r.json().get("current_weather", {})
        return {
            "temp": current.get("temperature"),
            "wind": current.get("windspeed"),
            "desc": WEATHER_CODES.get(current.get("weathercode"), "?"),
        }
    except (requests.RequestException, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Chile holidays (boostr.cl)
# --------------------------------------------------------------------------- #

def get_holidays(year):
    """
    List of Chilean holidays for 'year' via boostr.cl (free, no API key).
    Docs: https://boostr.cl/feriados
    Each item: {"date": "YYYY-MM-DD", "title": ..., "type": ..., "inalienable": bool}
    """
    try:
        r = requests.get(f"https://api.boostr.cl/holidays/{year}.json", timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "success":
            return None
        return data.get("data", [])
    except (requests.RequestException, ValueError):
        return None


def find_holiday_on(holidays, date_str):
    return next((h for h in holidays if h.get("date") == date_str), None)


def find_next_holiday(holidays, date_str):
    upcoming = sorted((h for h in holidays if h.get("date") > date_str), key=lambda h: h["date"])
    return upcoming[0] if upcoming else None


# --------------------------------------------------------------------------- #
# Screens
# --------------------------------------------------------------------------- #

def screen_boot():
    lcd_clear()
    lcd_message("AstronautMarkus", LCD_LINE_1)
    lcd_message("Dashboard Pi", LCD_LINE_2)
    sleep(2)


def screen_clock(duration):
    """Live clock: rewrites the time every TICK_SECONDS instead of staying static."""
    lcd_clear()
    for _ in range(int(duration / TICK_SECONDS)):
        now = datetime.now()
        lcd_message(now.strftime("%d/%m/%Y"), LCD_LINE_1)
        lcd_message(now.strftime("%H:%M:%S") + " Clock", LCD_LINE_2)
        sleep(TICK_SECONDS)


def screen_network(duration):
    lcd_loading("Network...")
    hostname = socket.gethostname()
    ip = get_local_ip()
    lcd_clear()
    lcd_message(hostname[:16], LCD_LINE_1)
    lcd_message(f"IP: {ip}", LCD_LINE_2)
    sleep(duration)


def screen_hardware(duration):
    """Live CPU/RAM/disk/temperature: re-read every TICK_SECONDS."""
    lcd_loading("Sensors...")
    lcd_clear()
    for _ in range(int(duration / TICK_SECONDS)):
        cpu = psutil.cpu_percent(interval=None)  # non-blocking: delta since last call
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
        temp = get_cpu_temp()
        temp_str = f"{temp:.1f}C" if temp is not None else "N/A"

        lcd_message(f"CPU:{cpu:.0f}% {temp_str}", LCD_LINE_1)
        lcd_message(f"RAM:{ram:.0f}% DSK:{disk:.0f}%", LCD_LINE_2)
        sleep(TICK_SECONDS)


def screen_weather(state):
    """
    'state' is a dict shared across loop iterations, so the weather and
    geolocation APIs aren't hit on every cycle (only every
    WEATHER_REFRESH_EVERY cycles, or if it hasn't been queried yet).
    """
    if state["location"] is None or state["cycle"] % WEATHER_REFRESH_EVERY == 0:
        lcd_loading("Locating...")
        state["location"] = get_location()

        if state["location"]:
            lcd_loading(f"Weather {state['location']['city']}"[:16])
            state["weather"] = get_weather(state["location"]["lat"], state["location"]["lon"])
        else:
            state["weather"] = None

    lcd_clear()
    location, weather = state["location"], state["weather"]

    if not location or not weather:
        lcd_message("Weather:", LCD_LINE_1)
        lcd_message("no connection", LCD_LINE_2)
    else:
        lcd_message(location["city"][:16], LCD_LINE_1)
        lcd_message(f"{weather['temp']:.0f}C {weather['desc']}"[:16], LCD_LINE_2)

    sleep(WEATHER_SECONDS)


def celebrate_holiday(title):
    """
    Celebration animation for when TODAY is a holiday: the title
    flashes between stars and the holiday name scrolls across the
    second line flanked by a custom star character (CGRAM).
    """
    lcd_clear()
    for _ in range(4):
        lcd_message("*" * 16, LCD_LINE_1)
        sleep(0.15)
        lcd_message(" HOLIDAY TODAY! ", LCD_LINE_1)
        sleep(0.35)

    scrolling = f"  {title}  " * 2
    for offset in range(len(title) + 4):
        window = scrolling[offset:offset + 14].ljust(14)[:14]
        lcd_write_at(0, LCD_LINE_2, [STAR_CHAR])
        lcd_write_at(1, LCD_LINE_2, [ord(c) for c in window])
        lcd_write_at(15, LCD_LINE_2, [STAR_CHAR])
        sleep(0.25)


def screen_holidays(state):
    """
    Queries the current year's holidays (once per year, cached in
    'state'). If TODAY is a holiday, celebrates via celebrate_holiday();
    otherwise shows the next holiday and how many days remain.
    """
    year = datetime.now().year
    if state["holidays_year"] != year:
        lcd_loading("Holidays CL...")
        state["holidays"] = get_holidays(year)
        state["holidays_year"] = year

    holidays = state["holidays"]
    if not holidays:
        lcd_clear()
        lcd_message("Holidays CL:", LCD_LINE_1)
        lcd_message("no connection", LCD_LINE_2)
        sleep(HOLIDAYS_SECONDS)
        return

    today = date.today()
    today_str = today.isoformat()

    today_holiday = find_holiday_on(holidays, today_str)
    if today_holiday:
        celebrate_holiday(today_holiday["title"])
        return

    next_holiday = find_next_holiday(holidays, today_str)
    lcd_clear()
    if next_holiday:
        days_left = (date.fromisoformat(next_holiday["date"]) - today).days
        lcd_message(next_holiday["title"][:16], LCD_LINE_1)
        lcd_message(f"In {days_left} days", LCD_LINE_2)
    else:
        lcd_message("Holidays CL:", LCD_LINE_1)
        lcd_message("none left", LCD_LINE_2)
    sleep(HOLIDAYS_SECONDS)


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #

def main():
    lcd_init()
    lcd_create_char(STAR_CHAR, STAR_BITMAP)
    lcd_byte(LCD_LINE_1, LCD_CMD)  # return to DDRAM after loading the custom char

    screen_boot()
    psutil.cpu_percent(interval=None)  # warm-up call so CPU deltas are meaningful

    state = {"location": None, "weather": None, "holidays": None, "holidays_year": None, "cycle": 0}

    try:
        while True:
            for screen in SCREENS:
                if screen == "clock":
                    screen_clock(CLOCK_SECONDS)
                elif screen == "network":
                    screen_network(NETWORK_SECONDS)
                elif screen == "hardware":
                    screen_hardware(HARDWARE_SECONDS)
                elif screen == "weather":
                    screen_weather(state)
                elif screen == "holidays":
                    screen_holidays(state)

            state["cycle"] += 1
    except KeyboardInterrupt:
        lcd_clear()
        lcd_message("Shutting down...", LCD_LINE_1)
        sleep(1)
        lcd_clear()


if __name__ == "__main__":
    main()
