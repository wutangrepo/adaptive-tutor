"""Database engine and session factory — SQLAlchemy 2.0 style."""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_default_db = Path(__file__).resolve().parent.parent / "app.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_default_db}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
