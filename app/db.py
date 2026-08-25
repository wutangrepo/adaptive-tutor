"""Database engine and session factory."""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Allow overriding DB location via DATABASE_URL env var (e.g. for tests).
# Default is a file `app.db` next to the project root.
_default_db = Path(__file__).resolve().parent.parent / "app.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_default_db}")

# SQLite needs check_same_thread=False for FastAPI's threaded workers.
# Use NullPool-friendly defaults; for a tiny tutor file DB the overhead is negligible.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    # Small tutor DB: conservative pool, fast startup.
    pool_pre_ping=True,
    future=True,
)

# expire_on_commit=False keeps objects usable after commit without re-query.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()
