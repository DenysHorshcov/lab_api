# ЩоВдягнути — вебсервіс прогнозу погоди та порад щодо одягу

Лабораторна робота 2 (Хмарні обчислення). Користувач вводить місто → сервіс бере прогноз з **Open-Meteo**,
**Google Gemini** перетворює його на поради (що вдягнути, парасоля, крем від сонця), а історія запитів і статистика
зберігаються в **Supabase (PostgreSQL)**. Розгортання — **Render**.

## Хмарні сервіси
| Модель | Сервіс | Роль |
|---|---|---|
| PaaS | Render | вебсервер FastAPI |
| DBaaS | Supabase | PostgreSQL |
| AIaaS | Google Gemini API | поради (structured JSON) |
| Data API | Open-Meteo | геокодинг і прогноз |

## Запуск локально
```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env                                  # заповніть GEMINI_API_KEY (DATABASE_URL — необов'язково)
uvicorn app.main:app --reload
```
Відкрийте http://127.0.0.1:8000 (інтерфейс) та http://127.0.0.1:8000/docs (Swagger).
Без `DATABASE_URL` використовується локальний SQLite; без `GEMINI_API_KEY` — запасні правила.

## Змінні середовища
| Змінна | Опис |
|---|---|
| `GEMINI_API_KEY` | ключ з Google AI Studio |
| `DATABASE_URL` | рядок підключення Supabase (`postgresql://...`) |
| `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL` | основна та запасна моделі (за замовчуванням `gemini-3.5-flash-lite` / `gemini-3.1-flash-lite`) |
| `WEATHER_CACHE_TTL` | кеш прогнозу, сек (600) |

## API
| Метод | Шлях | Призначення |
|---|---|---|
| GET | `/api/cities/search?q=` | пошук міста |
| GET | `/api/weather?lat=&lon=` | погода й прогноз на 5 днів |
| POST | `/api/advice` | прогноз + поради, запис в БД |
| GET | `/api/history?limit=` | історія запитів |
| GET | `/api/stats` | статистика (SQL `GROUP BY`) |
| GET/POST/DELETE | `/api/favorites` | улюблені міста |
| GET | `/api/health` | перевірка для Render |

Надійність порад: Gemini (основна модель) → запасна модель (429/5xx) → правила за порогами «відчувається як».

## Тести
```bash
pytest
```
Зовнішні API замокані.

## Розгортання на Render
1. Таблиці: виконайте `sql/schema.sql` у Supabase SQL Editor (або додаток створить їх сам).
2. Render → New Web Service → цей репозиторій (є `render.yaml`).
3. Env: `GEMINI_API_KEY`, `DATABASE_URL`. Health check: `/api/health`.
4. Безкоштовний план «засинає» після простою — відкрийте сайт за кілька хвилин до демо.

## Атрибуція
Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0). Умови безкоштовних планів Gemini/Supabase/Render перевіряйте на сайтах провайдерів.
