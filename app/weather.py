"""Клієнт Open-Meteo (геокодинг + прогноз) з простим кешем у пам'яті."""
import time

import httpx

from . import config
from .errors import CityNotFound, UpstreamError

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

CURRENT = "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m,weather_code"
DAILY = (
    "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
    "apparent_temperature_min,precipitation_probability_max,uv_index_max"
)

_cache: dict[tuple[float, float], tuple[float, dict]] = {}
_geo_cache: dict[str, list[dict]] = {}

WMO = {
    0: "Ясно", 1: "Переважно ясно", 2: "Мінлива хмарність", 3: "Хмарно",
    45: "Туман", 48: "Паморозний туман",
    51: "Легка мряка", 53: "Мряка", 55: "Сильна мряка",
    56: "Паморозна мряка", 57: "Сильна паморозна мряка",
    61: "Невеликий дощ", 63: "Дощ", 65: "Сильний дощ",
    66: "Крижаний дощ", 67: "Сильний крижаний дощ",
    71: "Невеликий сніг", 73: "Сніг", 75: "Сильний сніг", 77: "Снігові зерна",
    80: "Невеликі зливи", 81: "Зливи", 82: "Сильні зливи",
    85: "Снігові зливи", 86: "Сильні снігові зливи",
    95: "Гроза", 96: "Гроза з градом", 99: "Сильна гроза з градом",
}


def describe(code: int | None) -> str:
    return WMO.get(code, "Невідомо") if code is not None else "Невідомо"


RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_DELAYS = (1.0, 2.5, 5.0)  # пауза перед повторами, сек


def _get(url: str, params: dict) -> dict:
    """GET з повторами: спільні IP хостингу часто впираються в ліміт Open-Meteo (429)."""
    last: UpstreamError | None = None
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            r = httpx.get(url, params=params, timeout=config.HTTP_TIMEOUT,
                          headers={"User-Agent": "weather-outfit-advisor/1.0 (student project)"})
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            msg = "забагато запитів, спробуйте за хвилину" if code == 429 else f"HTTP {code}"
            last = UpstreamError("open-meteo", msg, code)
            if code not in RETRY_STATUSES:
                raise last from e
        except (httpx.HTTPError, ValueError) as e:
            last = UpstreamError("open-meteo", f"недоступний: {e.__class__.__name__}")
        if attempt < len(RETRY_DELAYS):
            time.sleep(RETRY_DELAYS[attempt])
    raise last


def search_cities(q: str, count: int = 5) -> list[dict]:
    key = q.strip().lower()
    if key in _geo_cache:
        return _geo_cache[key]
    data = _get(GEOCODING_URL, {"name": q, "count": count, "language": "uk", "format": "json"})
    results = data.get("results") or []
    if not results:
        raise CityNotFound(q)
    found = [
        {
            "name": r["name"],
            "country": r.get("country"),
            "admin1": r.get("admin1"),
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "timezone": r.get("timezone"),
        }
        for r in results
    ]
    _geo_cache[key] = found
    return found


def get_weather(lat: float, lon: float) -> dict:
    key = (round(lat, 3), round(lon, 3))
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < config.WEATHER_CACHE_TTL:
        return hit[1]

    raw = _get(
        FORECAST_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "current": CURRENT,
            "daily": DAILY,
            "timezone": "auto",
            "forecast_days": 5,
        },
    )
    cur = raw.get("current") or {}
    daily = raw.get("daily") or {}
    days = []
    for i, date in enumerate(daily.get("time", [])):
        days.append(
            {
                "date": date,
                "weather_code": daily["weather_code"][i],
                "description": describe(daily["weather_code"][i]),
                "temp_max": daily["temperature_2m_max"][i],
                "temp_min": daily["temperature_2m_min"][i],
                "feels_max": daily["apparent_temperature_max"][i],
                "feels_min": daily["apparent_temperature_min"][i],
                "precip_probability": daily["precipitation_probability_max"][i],
                "uv_index": daily["uv_index_max"][i],
            }
        )
    today = days[0] if days else {}
    result = {
        "timezone": raw.get("timezone"),
        "current": {
            "temperature": cur.get("temperature_2m"),
            "feels_like": cur.get("apparent_temperature"),
            "humidity": cur.get("relative_humidity_2m"),
            "precipitation": cur.get("precipitation"),
            "wind_speed": cur.get("wind_speed_10m"),
            "weather_code": cur.get("weather_code"),
            "description": describe(cur.get("weather_code")),
        },
        "today": {
            "precip_probability": today.get("precip_probability"),
            "uv_index": today.get("uv_index"),
            "temp_max": today.get("temp_max"),
            "temp_min": today.get("temp_min"),
        },
        "daily": days,
        "attribution": "Weather data by Open-Meteo.com (CC BY 4.0)",
    }
    _cache[key] = (now, result)
    return result


def clear_cache() -> None:
    _cache.clear()
    _geo_cache.clear()
