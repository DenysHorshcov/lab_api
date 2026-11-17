from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config

_url = config.DATABASE_URL
for _prefix in ("postgres://", "postgresql://"):
    if _url.startswith(_prefix):
        # явно psycopg2: нові версії SQLAlchemy за замовчуванням шукають psycopg (v3)
        _url = "postgresql+psycopg2://" + _url[len(_prefix):]
        break

_kwargs = {"connect_args": {"check_same_thread": False}} if _url.startswith("sqlite") else {"pool_pre_ping": True}
engine = create_engine(_url, **_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
