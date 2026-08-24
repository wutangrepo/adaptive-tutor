import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models import Assessment, AuditLog, HintDraft  # noqa: E402

out = []
with SessionLocal() as db:
    for h in db.query(HintDraft).all():
        out.append(f"hint {h.id} item={h.item_id} status={h.status}: {(h.text or '')[:60]}")
    for a in db.query(Assessment).all():
        out.append(f"assessment {a.id} item={a.item_id} status={a.status} "
                   f"score={a.ai_total}/{a.ai_max} conf={a.ai_confidence} final={a.final_total}")
    for l in db.query(AuditLog).order_by(AuditLog.id).all():
        out.append(f"audit {l.created_at} actor={l.actor} action={l.action} "
                   f"target={l.target} detail={l.detail}")

print("\n".join(out) if out else "DB: no AI-review rows yet")
