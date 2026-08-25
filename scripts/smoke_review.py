"""In-process smoke test — hint draft → approve → audit (requires Ollama)."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.main import COOKIE_NAME, _professor_token, hint_draft, review_hint  # noqa: E402
from app.models import AuditLog, HintDraft  # noqa: E402

PROF = SimpleNamespace(cookies={COOKIE_NAME: _professor_token()})
results: list[bool] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f" — {extra}" if extra else ""), flush=True)


r = hint_draft("ex9-8-1", PROF)  # type: ignore[arg-type]
with SessionLocal() as db:
    h = db.query(HintDraft).order_by(HintDraft.id.desc()).first()
check("hint drafted", h is not None and h.status == "draft" and bool(h.text), repr((h.text or "")[:70]))

if h:
    review_hint(h.id, PROF, action="approved")  # type: ignore[arg-type]
    with SessionLocal() as db:
        s = db.get(HintDraft, h.id).status  # type: ignore[union-attr]
    check("hint approved", s == "approved")

    review_hint(h.id, PROF, action="rejected")  # type: ignore[arg-type]
    with SessionLocal() as db:
        s = db.get(HintDraft, h.id).status  # type: ignore[union-attr]
    check("illegal transition blocked", s == "approved")

with SessionLocal() as db:
    actors = [row.actor for row in db.query(AuditLog).all()]
check("audit has AI + professor", any(a.startswith("ollama:") for a in actors) and "professor" in actors, ", ".join(sorted(set(actors))) or "no audit rows")

print("\n" + ("ALL SMOKE TESTS PASSED" if all(results) else "SOME CHECKS FAILED"))
sys.exit(0 if all(results) else 1)
