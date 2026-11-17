"""Поради щодо одягу: Gemini (основна → запасна модель) → правила."""
import json

import httpx

from . import config
from .errors import UpstreamError
from .schemas import Advice, Profile

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRY_STATUSES = {429, 500, 502, 503, 504}

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "outfit": {
            "type": "OBJECT",
            "properties": {
                "head": {"type": "STRING"},
                "top": {"type": "STRING"},
                "bottom": {"type": "STRING"},
                "shoes": {"type": "STRING"},
            },
            "required": ["head", "top", "bottom", "shoes"],
        },
        "umbrella": {"type": "BOOLEAN"},
        "sunscreen": {"type": "BOOLEAN"},
        "warnings": {"type": "ARRAY", "items": {"type": "STRING"}},
        "tips": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["summary", "outfit", "umbrella", "sunscreen", "warnings", "tips"],
}

ACTIVITY_UK = {"walk": "прогулянка", "run": "біг", "office": "офіс/міські справи",
               "cycling": "велосипед", "hiking": "похід"}
COLD_UK = {"low": "мало мерзне", "normal": "звичайна", "high": "дуже мерзне"}


def build_prompt(city: str, weather: dict, profile: Profile) -> str:
    cur, today = weather["current"], weather["today"]
    return (
        "Ти — помічник, що радить, що вдягнути. Відповідай українською, коротко і конкретно.\n"
        f"Місто: {city}\n"
        f"Зараз: {cur['temperature']}°C, відчувається як {cur['feels_like']}°C, "
        f"{cur['description']}, вітер {cur['wind_speed']} км/год, вологість {cur['humidity']}%.\n"
        f"Сьогодні: {today['temp_min']}…{today['temp_max']}°C, ймовірність опадів "
        f"{today['precip_probability']}%, максимальний UV-індекс {today['uv_index']}.\n"
        f"Активність: {ACTIVITY_UK[profile.activity]}. Чутливість до холоду: {COLD_UK[profile.cold_sensitivity]}.\n"
        "Дай поради за схемою: summary, outfit (head/top/bottom/shoes), umbrella, sunscreen, "
        "warnings (небезпечні умови), tips."
    )


def _call_gemini(model: str, prompt: str) -> Advice:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0.4,
        },
    }
    try:
        r = httpx.post(
            GEMINI_URL.format(model=model),
            json=body,
            headers={"x-goog-api-key": config.GEMINI_API_KEY},
            timeout=config.HTTP_TIMEOUT * 2,
        )
    except httpx.HTTPError as e:
        raise UpstreamError("gemini", f"недоступний: {e.__class__.__name__}", 503) from e
    if r.status_code != 200:
        raise UpstreamError("gemini", f"HTTP {r.status_code}", r.status_code)
    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return Advice.model_validate(json.loads(text))
    except (KeyError, IndexError, ValueError) as e:
        raise UpstreamError("gemini", "некоректна відповідь моделі", 502) from e


def rule_based_advice(weather: dict, profile: Profile) -> Advice:
    """Запасний варіант без AI: правила за порогами «відчувається як»."""
    cur, today = weather["current"], weather["today"]
    feels = cur["feels_like"] if cur["feels_like"] is not None else (cur["temperature"] or 0)
    feels += {"low": 3, "normal": 0, "high": -4}[profile.cold_sensitivity]
    if profile.activity in ("run", "cycling", "hiking"):
        feels += 4  # під час руху стає тепліше
    precip = today.get("precip_probability") or 0
    uv = today.get("uv_index") or 0
    wind = cur.get("wind_speed") or 0

    if feels < -10:
        top, bottom, head, shoes = "термобілизна + светр + пуховик", "утеплені штани", "тепла шапка, шарф", "зимові черевики"
    elif feels < 0:
        top, bottom, head, shoes = "светр + пуховик", "утеплені штани", "шапка", "теплі черевики"
    elif feels < 10:
        top, bottom, head, shoes = "светр + куртка", "джинси", "легка шапка за потреби", "закрите взуття"
    elif feels < 18:
        top, bottom, head, shoes = "толстовка або легка куртка", "джинси", "без головного убору", "кросівки"
    elif feels < 25:
        top, bottom, head, shoes = "футболка + легка кофта", "джинси або шорти", "без головного убору", "кросівки"
    else:
        top, bottom, head, shoes = "легка футболка", "шорти", "кепка", "легке відкрите взуття"

    umbrella = precip >= 40
    sunscreen = uv >= 3
    if umbrella:
        shoes += " (водонепроникне)"
    warnings = []
    if wind >= 40:
        warnings.append("Сильний вітер")
    if uv >= 8:
        warnings.append("Дуже високий UV-індекс")
    if precip >= 70:
        warnings.append("Висока ймовірність опадів")
    return Advice(
        summary=f"{cur['description']}, відчувається як {cur['feels_like']}°C (поради за правилами)",
        outfit={"head": head, "top": top, "bottom": bottom, "shoes": shoes},
        umbrella=umbrella,
        sunscreen=sunscreen,
        warnings=warnings,
        tips=["Одягайтеся шарами"] if feels < 10 else [],
    )


def get_advice(city: str, weather: dict, profile: Profile) -> tuple[Advice, str]:
    """Повертає (поради, джерело: назва моделі або 'rules')."""
    if config.GEMINI_API_KEY:
        prompt = build_prompt(city, weather, profile)
        models = [config.GEMINI_MODEL]
        if config.GEMINI_FALLBACK_MODEL and config.GEMINI_FALLBACK_MODEL != config.GEMINI_MODEL:
            models.append(config.GEMINI_FALLBACK_MODEL)
        for model in models:
            try:
                return _call_gemini(model, prompt), model
            except UpstreamError as e:
                if e.status in RETRY_STATUSES:
                    continue  # пробуємо запасну модель
                break  # 4xx (ключ, запит) — запасна модель не допоможе
    return rule_based_advice(weather, profile), "rules"
