-- Схема для Supabase (SQL Editor). Додаток також створює таблиці сам при старті.
CREATE TABLE IF NOT EXISTS cities (
    id        SERIAL PRIMARY KEY,
    name      TEXT NOT NULL,
    country   TEXT,
    admin1    TEXT,
    latitude  DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    timezone  TEXT,
    UNIQUE (latitude, longitude)
);

CREATE TABLE IF NOT EXISTS requests (
    id                 SERIAL PRIMARY KEY,
    city_id            INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    temperature        DOUBLE PRECISION,
    feels_like         DOUBLE PRECISION,
    precip_probability DOUBLE PRECISION,
    wind_speed         DOUBLE PRECISION,
    uv_index           DOUBLE PRECISION,
    weather_code       INTEGER,
    advice             JSONB,
    model_used         TEXT,
    latency_ms         INTEGER
);

CREATE TABLE IF NOT EXISTS favorites (
    id         SERIAL PRIMARY KEY,
    city_id    INTEGER NOT NULL UNIQUE REFERENCES cities(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
