"""Seed DB from data/items.json with deterministic expected values."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import proplog  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Item  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"


def derive_expected(rec: dict):
    p = rec["payload"]
    t = rec["type"]
    if t == "logic_eval":
        return proplog.evaluate(p["formula"], p["assignment"])
    if t == "tautology_check":
        return proplog.is_tautology(p["formula"])
    if t == "equivalence_check":
        return proplog.are_equivalent(p["formula1"], p["formula2"])
    if t == "mcq":
        return p["options"][p["answer_index"]]
    raise ValueError(f"unknown item type {t!r}")


def main(reset: bool = True):
    Base.metadata.create_all(bind=engine)
    items = json.loads((DATA / "items.json").read_text(encoding="utf-8"))
    with SessionLocal() as db:
        if reset:
            db.query(Item).delete()
        for rec in items:
            expected = derive_expected(rec)
            print(f"  {rec['id']:>14}  expected = {expected}")
            db.merge(Item(**rec))  # upsert
        db.commit()
    print(f"seeded {len(items)} items into {engine.url}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Seed adaptive-tutor DB")
    ap.add_argument("--append", action="store_true", help="don't delete existing items")
    args = ap.parse_args()
    main(reset=not args.append)
