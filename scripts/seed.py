import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import engine, SessionLocal, Base
from app.models import Item
from app import proplog

DATA = Path(__file__).resolve().parent.parent / "data"


def derive_expected(rec):
    p = rec["payload"]
    if rec["type"] == "logic_eval":
        return proplog.evaluate(p["formula"], p["assignment"])
    if rec["type"] == "tautology_check":
        return proplog.is_tautology(p["formula"])
    if rec["type"] == "equivalence_check":
        return proplog.are_equivalent(p["formula1"], p["formula2"])
    if rec["type"] == "mcq":
        return p["options"][p["answer_index"]]
    return None

def main():
    Base.metadata.create_all(engine)
    items = json.loads((DATA / "items.json").read_text(encoding="utf-8"))
    with SessionLocal() as db:
        db.query(Item).delete()
        for rec in items:
            print(f"  {rec['id']:>10}  expected = {derive_expected(rec)}")
            db.add(Item(**rec))
        db.commit()
    print(f"seeded {len(items)} items")


if __name__ == "__main__":
    main()