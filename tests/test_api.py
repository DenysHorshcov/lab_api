import httpx
import pytest

from app import advisor, weather
from app.schemas import Profile
from tests.conftest import FORECAST, GEMINI_OK, GEO, FakeResponse

CITY = {"latitude": 50.45, "longitude": 30.52, "name": "Київ", "country": "Україна"}


@pytest.fixture()
def mock_http(monkeypatch):
    calls = {"gemini": []}

    def fake_get(url, params=None, timeout=None):
        if "geocoding" in url:
            if params["name"] == "Nowhere":
                return FakeResponse(200, {})
            return FakeResponse(200, GEO)
        return FakeResponse(200, FORECAST)

    def fake_post(url, json=None, headers=None, timeout=None):
        model = url.split("/models/")[1].split(":")[0]
        calls["gemini"].append(model)
        handler = calls.get("handler")
        return handler(model) if handler else FakeResponse(200, GEMINI_OK)

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    return calls


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_city_search(client, mock_http):
    r = client.get("/api/cities/search", params={"q": "Київ"})
    assert r.status_code == 200 and r.json()[0]["name"] == "Київ"


def test_city_not_found(client, mock_http):
    r = client.get("/api/cities/search", params={"q": "Nowhere"})
    assert r.status_code == 404


def test_invalid_coordinates(client):
    assert client.get("/api/weather", params={"lat": 123, "lon": 10}).status_code == 422


def test_weather_parsed_and_cached(client, mock_http, monkeypatch):
    n = {"c": 0}
    orig = httpx.get

    def counting(url, params=None, timeout=None):
        n["c"] += 1
        return orig(url, params=params, timeout=timeout)

    monkeypatch.setattr(httpx, "get", counting)
    a = client.get("/api/weather", params={"lat": 50.45, "lon": 30.52}).json()
    client.get("/api/weather", params={"lat": 50.45, "lon": 30.52})
    assert n["c"] == 1  # другий запит із кешу
    assert a["current"]["description"] == "Невеликий дощ" and len(a["daily"]) == 2


def test_advice_saved_and_stats(client, mock_http):
    r = client.post("/api/advice", json=CITY)
    assert r.status_code == 200
    body = r.json()
    assert body["advice"]["umbrella"] is True and body["model_used"] == "gemini-3.5-flash-lite"
    client.post("/api/advice", json=CITY)
    hist = client.get("/api/history").json()
    assert len(hist) == 2 and hist[0]["city"] == "Київ"
    s = client.get("/api/stats").json()
    assert s["total_requests"] == 2 and s["top_cities"][0]["requests"] == 2
    assert s["rainy_share"] == 1.0


def test_gemini_fallback_model(client, mock_http):
    mock_http["handler"] = lambda m: FakeResponse(503) if m == "gemini-3.5-flash-lite" else FakeResponse(200, GEMINI_OK)
    body = client.post("/api/advice", json=CITY).json()
    assert body["model_used"] == "gemini-3.1-flash-lite"
    assert mock_http["gemini"] == ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]


def test_rules_when_gemini_down(client, mock_http):
    mock_http["handler"] = lambda m: FakeResponse(429)
    body = client.post("/api/advice", json=CITY).json()
    assert body["model_used"] == "rules" and body["advice"]["umbrella"] is True


def test_no_fallback_on_auth_error(client, mock_http):
    mock_http["handler"] = lambda m: FakeResponse(403)
    body = client.post("/api/advice", json=CITY).json()
    assert body["model_used"] == "rules" and len(mock_http["gemini"]) == 1


def test_open_meteo_down_returns_502(client, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", boom)
    r = client.post("/api/advice", json=CITY)
    assert r.status_code == 502


def test_favorites_flow(client):
    r = client.post("/api/favorites", json=CITY)
    assert r.status_code == 201
    cid = r.json()["id"]
    client.post("/api/favorites", json=CITY)  # дубль ігнорується
    assert len(client.get("/api/favorites").json()) == 1
    assert client.delete(f"/api/favorites/{cid}").status_code == 204
    assert client.delete(f"/api/favorites/{cid}").status_code == 404


def test_rule_advice_cold_vs_hot():
    w = {"current": {"feels_like": -15, "temperature": -12, "wind_speed": 5, "description": "Сніг"},
         "today": {"precip_probability": 10, "uv_index": 0}}
    assert "пуховик" in advisor.rule_based_advice(w, Profile()).outfit.top
    w["current"]["feels_like"] = 30
    w["today"]["uv_index"] = 9
    a = advisor.rule_based_advice(w, Profile())
    assert a.sunscreen and "футболка" in a.outfit.top
