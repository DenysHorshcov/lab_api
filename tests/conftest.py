import os

os.environ["DATABASE_URL"] = "sqlite:///test.db"
os.environ["GEMINI_API_KEY"] = "test-key"

import pytest
from fastapi.testclient import TestClient

from app import weather
from app.db import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    weather.clear_cache()
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)
    engine.dispose()
    if os.path.exists("test.db"):
        os.remove("test.db")


class FakeResponse:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        import httpx
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)


GEO = {"results": [{"name": "Київ", "country": "Україна", "admin1": "Київ", "latitude": 50.45,
                    "longitude": 30.52, "timezone": "Europe/Kyiv"}]}

FORECAST = {
    "timezone": "Europe/Kyiv",
    "current": {"temperature_2m": 5.0, "apparent_temperature": 2.0, "relative_humidity_2m": 80,
                "precipitation": 0.0, "wind_speed_10m": 12.0, "weather_code": 61},
    "daily": {
        "time": ["2026-11-17", "2026-11-18"],
        "weather_code": [61, 3],
        "temperature_2m_max": [7.0, 8.0], "temperature_2m_min": [1.0, 2.0],
        "apparent_temperature_max": [5.0, 6.0], "apparent_temperature_min": [-1.0, 0.0],
        "precipitation_probability_max": [80, 20], "uv_index_max": [1.0, 1.5],
    },
}

GEMINI_OK = {"candidates": [{"content": {"parts": [{"text": (
    '{"summary":"Прохолодно, дощ","outfit":{"head":"шапка","top":"куртка","bottom":"джинси",'
    '"shoes":"водонепроникне взуття"},"umbrella":true,"sunscreen":false,'
    '"warnings":[],"tips":["Візьміть парасолю"]}')}]}}]}
