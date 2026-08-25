"""Row counts for quick sanity check."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models import Attempt, AuditLog, HintDraft, Item  # noqa: E402

with SessionLocal() as db:
    counts = {
        "items": db.query(Item).count(),
        "attempts": db.query(Attempt).count(),
        "hint_drafts": db.query(HintDraft).count(),
        "audit_log": db.query(AuditLog).count(),
    }
for k, v in counts.items():
    print(f"{k:>12}: {v}")
