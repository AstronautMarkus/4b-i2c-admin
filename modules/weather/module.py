import time

from core.config import WEATHER_CACHE_SECONDS
from core.http_utils import get_json
from core.module_base import BaseModule

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Fog",
    51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Showers", 81: "Showers", 82: "Heavy showers",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm",
}


def get_location():
    """Approximate geolocation by public IP (no API key, no setup required)."""
    data = get_json("https://ipwho.is/")
    if not data or not data.get("success", False):
        return None
    return {
        "city": data.get("city", "?"),
        "lat": data.get("latitude"),
        "lon": data.get("longitude"),
    }


def get_weather(lat, lon):
    """Current weather via Open-Meteo (free, no API key)."""
    data = get_json(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": lat, "longitude": lon, "current_weather": True},
    )
    if data is None:
        return None
    current = data.get("current_weather", {})
    return {
        "temp": current.get("temperature"),
        "wind": current.get("windspeed"),
        "desc": WEATHER_CODES.get(current.get("weathercode"), "?"),
    }


class Module(BaseModule):
    def tick(self, ctx):
        cache = ctx.cache
        stale = cache.get("fetched_at") is None or (
            time.time() - cache["fetched_at"] > WEATHER_CACHE_SECONDS
        )

        if stale:
            location = get_location()
            weather = get_weather(location["lat"], location["lon"]) if location else None
            cache["location"] = location
            cache["weather"] = weather
            cache["fetched_at"] = time.time()

        location, weather = cache.get("location"), cache.get("weather")
        if not location or not weather:
            return "Weather:", "no connection"

        return location["city"][:16], f"{weather['temp']:.0f}C {weather['desc']}"[:16]
