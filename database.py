"""Database setup.

Production: DATABASE_URL (Postgres). Local dev: SQLite fallback.
No secret is hardcoded here; everything comes from the environment.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_raw = os.environ.get("DATABASE_URL", "").strip()
if _raw.startswith("postgres://"):
    _raw = _raw.replace("postgres://", "postgresql+psycopg://", 1)
if _raw.startswith("postgresql://") and "+psycopg" not in _raw:
    _raw = _raw.replace("postgresql://", "postgresql+psycopg://", 1)

DATABASE_URL = _raw or "sqlite:///./dayforge.db"
CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=CONNECT_ARGS)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
