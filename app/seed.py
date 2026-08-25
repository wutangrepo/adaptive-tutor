"""Seeding concern — isolated from routes/db setup."""

import json
import logging
from pathlib import Path
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine
from .models import Item

log = logging.getLogger(__name__)
DATA = Path(__file__).resolve().parent.parent / "data"


def seed_if_empty(db: Session | None = None) -> int:
    """Seed items.json if table empty. Returns number seeded (0 if already populated)."""
    close_after = False
    if db is None:
        db = SessionLocal()
        close_after = True
    try:
        if db.query(Item).count() > 0:
            return 0
        path = DATA / "items.json"
        if not path.exists():
            log.warning("seed: %s not found", path)
            return 0
        items = json.loads(path.read_text(encoding="utf-8"))
        for rec in items:
            db.add(Item(**rec))
        db.commit()
        log.info("seeded %d items", len(items))
        return len(items)
    finally:
        if close_after:
            db.close()


def ensure_db() -> None:
    """Create tables + seed if empty. Safe to call at import/startup."""
    Base.metadata.create_all(bind=engine)
    try:
        seed_if_empty()
    except Exception as e:  # noqa: BLE001
        log.warning("seed check failed: %s", e)


if __name__ == "__main__":
    ensure_db()
