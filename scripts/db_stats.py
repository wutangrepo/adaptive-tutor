import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models import (Assessment, Attempt, AuditLog, HintDraft,  # noqa: E402
                        Item)

with SessionLocal() as db:
    counts = {
        "items": db.query(Item).count(),
        "attempts": db.query(Attempt).count(),
        "assessments": db.query(Assessment).count(),
        "hint_drafts": db.query(HintDraft).count(),
        "audit_log": db.query(AuditLog).count(),
    }
for name, n in counts.items():
    print(f"{name:>12}: {n}")
