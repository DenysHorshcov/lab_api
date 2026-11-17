from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CityOut(BaseModel):
    id: int | None = None
    name: str
    country: str | None = None
    admin1: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str | None = None


class Profile(BaseModel):
    activity: Literal["walk", "run", "office", "cycling", "hiking"] = "walk"
    cold_sensitivity: Literal["low", "normal", "high"] = "normal"


class AdviceRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    name: str = Field(min_length=1, max_length=120)
    country: str | None = None
    admin1: str | None = None
    timezone: str | None = None
    profile: Profile = Profile()


class Outfit(BaseModel):
    head: str
    top: str
    bottom: str
    shoes: str


class Advice(BaseModel):
    summary: str
    outfit: Outfit
    umbrella: bool
    sunscreen: bool
    warnings: list[str] = []
    tips: list[str] = []


class AdviceResponse(BaseModel):
    request_id: int
    city: CityOut
    weather: dict
    advice: Advice
    model_used: str
    latency_ms: int


class FavoriteIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    name: str = Field(min_length=1, max_length=120)
    country: str | None = None
    admin1: str | None = None
    timezone: str | None = None


class HistoryItem(BaseModel):
    id: int
    city: str
    country: str | None
    created_at: datetime
    temperature: float | None
    feels_like: float | None
    weather_code: int | None
    model_used: str | None
    latency_ms: int | None
    advice: dict | None
