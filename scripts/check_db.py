"""Pretty-print hints + audit trail."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models import AuditLog, HintDraft  # noqa: E402

out: list[str] = []
with SessionLocal() as db:
    for h in db.query(HintDraft).order_by(HintDraft.id).all():
        out.append(f"hint {h.id:>3} {h.status:<8} item={h.item_id:<14} {h.text[:70]}")
    for l in db.query(AuditLog).order_by(AuditLog.id).all():
        detail = f" {l.detail}" if l.detail else ""
        out.append(f"audit {l.created_at:%Y-%m-%d %H:%M} {l.actor:<18} {l.action:<16} {l.target}{detail}")

print("\n".join(out) if out else "DB: no hints/audit rows yet")
