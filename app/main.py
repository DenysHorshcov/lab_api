import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from . import advisor, weather
from .db import get_db, init_db
from .errors import CityNotFound, UpstreamError
from .models import City, Favorite, Request
from .schemas import AdviceRequest, AdviceResponse, CityOut, FavoriteIn, HistoryItem

STATIC = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ЩоВдягнути API",
    description="Прогноз погоди (Open-Meteo) і поради щодо одягу (Google Gemini).",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(UpstreamError)
def upstream_handler(_, exc: UpstreamError):
    return JSONResponse(status_code=502, content={"detail": f"{exc.service}: {exc.message}"})


@app.exception_handler(CityNotFound)
def city_handler(_, exc: CityNotFound):
    return JSONResponse(status_code=404, content={"detail": f"Місто «{exc}» не знайдено"})


def _get_or_create_city(db: Session, data) -> City:
    lat, lon = round(data.latitude, 4), round(data.longitude, 4)
    city = db.scalar(select(City).where(City.latitude == lat, City.longitude == lon))
    if city is None:
        city = City(name=data.name, country=data.country, admin1=data.admin1,
                    latitude=lat, longitude=lon, timezone=data.timezone)
        db.add(city)
        db.flush()
    return city


def _city_out(c: City) -> CityOut:
    return CityOut(id=c.id, name=c.name, country=c.country, admin1=c.admin1,
                   latitude=c.latitude, longitude=c.longitude, timezone=c.timezone)


@app.get("/api/health", tags=["service"])
def health():
    return {"status": "ok"}


@app.get("/api/cities/search", response_model=list[CityOut], tags=["weather"])
def search_cities(q: str = Query(min_length=2, max_length=100)):
    return weather.search_cities(q)


@app.get("/api/weather", tags=["weather"])
def get_weather(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)):
    return weather.get_weather(lat, lon)


@app.post("/api/advice", response_model=AdviceResponse, tags=["advice"])
def create_advice(body: AdviceRequest, db: Session = Depends(get_db)):
    started = time.perf_counter()
    w = weather.get_weather(body.latitude, body.longitude)
    advice, model = advisor.get_advice(body.name, w, body.profile)
    latency = int((time.perf_counter() - started) * 1000)

    city = _get_or_create_city(db, body)
    cur, today = w["current"], w["today"]
    req = Request(
        city_id=city.id, temperature=cur["temperature"], feels_like=cur["feels_like"],
        precip_probability=today["precip_probability"], wind_speed=cur["wind_speed"],
        uv_index=today["uv_index"], weather_code=cur["weather_code"],
        advice=advice.model_dump(), model_used=model, latency_ms=latency,
    )
    db.add(req)
    db.commit()
    return AdviceResponse(request_id=req.id, city=_city_out(city), weather=w,
                          advice=advice, model_used=model, latency_ms=latency)


@app.get("/api/history", response_model=list[HistoryItem], tags=["stats"])
def history(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    rows = db.scalars(select(Request).order_by(Request.id.desc()).limit(limit)).all()
    return [
        HistoryItem(id=r.id, city=r.city.name, country=r.city.country, created_at=r.created_at,
                    temperature=r.temperature, feels_like=r.feels_like, weather_code=r.weather_code,
                    model_used=r.model_used, latency_ms=r.latency_ms, advice=r.advice)
        for r in rows
    ]


@app.get("/api/stats", tags=["stats"])
def stats(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(Request.id))) or 0
    top_cities = db.execute(
        select(City.name, City.country, func.count(Request.id).label("requests"),
               func.avg(Request.feels_like).label("avg_feels_like"))
        .join(Request, Request.city_id == City.id)
        .group_by(City.id, City.name, City.country)
        .order_by(func.count(Request.id).desc())
        .limit(5)
    ).all()
    rainy = db.scalar(select(func.avg(case((Request.precip_probability >= 50, 1.0), else_=0.0)))) or 0
    day = func.date(Request.created_at)
    per_day = db.execute(
        select(day.label("day"), func.count(Request.id)).group_by(day).order_by(day.desc()).limit(14)
    ).all()
    models = db.execute(
        select(Request.model_used, func.count(Request.id)).group_by(Request.model_used)
    ).all()
    avg_latency = db.scalar(select(func.avg(Request.latency_ms)))
    return {
        "total_requests": total,
        "avg_latency_ms": round(avg_latency) if avg_latency else None,
        "rainy_share": round(float(rainy), 3),
        "top_cities": [
            {"name": n, "country": c, "requests": k, "avg_feels_like": round(a, 1) if a is not None else None}
            for n, c, k, a in top_cities
        ],
        "requests_per_day": [{"day": str(d), "count": k} for d, k in reversed(per_day)],
        "models": [{"model": m or "?", "count": k} for m, k in models],
    }


@app.get("/api/favorites", response_model=list[CityOut], tags=["favorites"])
def list_favorites(db: Session = Depends(get_db)):
    rows = db.scalars(select(Favorite).order_by(Favorite.id.desc())).all()
    return [_city_out(f.city) for f in rows]


@app.post("/api/favorites", response_model=CityOut, status_code=201, tags=["favorites"])
def add_favorite(body: FavoriteIn, db: Session = Depends(get_db)):
    city = _get_or_create_city(db, body)
    if db.scalar(select(Favorite).where(Favorite.city_id == city.id)) is None:
        db.add(Favorite(city_id=city.id))
    db.commit()
    return _city_out(city)


@app.delete("/api/favorites/{city_id}", status_code=204, tags=["favorites"])
def remove_favorite(city_id: int, db: Session = Depends(get_db)):
    fav = db.scalar(select(Favorite).where(Favorite.city_id == city_id))
    if fav is None:
        raise HTTPException(404, "Немає в улюблених")
    db.delete(fav)
    db.commit()


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")
