"""Direct smoke test: calls the route functions in-process (no HTTP server).

Requires Ollama running -- makes two real qwen calls.
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.main import (COOKIE_NAME, _professor_token, assess_draft,  # noqa: E402
                      hint_draft, review_assessment, review_hint)
from app.models import Assessment, AuditLog, HintDraft  # noqa: E402

# professor-authorized request shim for calling the guarded routes directly
PROF = SimpleNamespace(cookies={COOKIE_NAME: _professor_token()})

results = []


def check(name, ok, extra=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f" -- {extra}" if extra else ""), flush=True)


def latest_hint():
    with SessionLocal() as db:
        return db.query(HintDraft).order_by(HintDraft.id.desc()).first()


# 1) draft a real hint via qwen
r = hint_draft("ex9-8-1", PROF)
with SessionLocal() as db:
    h = db.query(HintDraft).order_by(HintDraft.id.desc()).first()
    hid, hstatus, htext = h.id, h.status, h.text
check("hint drafted by live model",
      h is not None and hstatus == "draft" and bool(htext),
      repr((htext or "")[:70]) if h else "")

# 2) professor approves the hint
review_hint(hid, PROF, action="approved")
with SessionLocal() as db:
    status_now = db.get(HintDraft, hid).status
check("hint approved via FSM", status_now == "approved")

# 3) illegal transition rejected (approved -> rejected must fail)
review_hint(hid, PROF, action="rejected")
with SessionLocal() as db:
    status_now = db.get(HintDraft, hid).status
check("illegal transition blocked", status_now == "approved")

# 4) AI grade draft for a free-text answer (second real qwen call)
asyncio.run(assess_draft("ex9-9-6", sid="smoke",
                         answer_text="By De Morgan's law, negating a "
                                     "conjunction negates both parts and "
                                     "turns AND into OR."))
with SessionLocal() as db:
    a = (db.query(Assessment).filter_by(learner_id="smoke")
         .order_by(Assessment.id.desc()).first())
    aid = a.id if a else None
    a_status, a_total, a_max, a_conf = (a.status, a.ai_total, a.ai_max,
                                        a.ai_confidence) if a else (None,) * 4
assess_ok = (a is not None and a_status in ("pending", "needs_human")
             and a_max == 3)
check("AI grade drafted into Assessment", assess_ok,
      (f"status={a_status} score={a_total}/{a_max} conf={a_conf}"
       if assess_ok else "no assessment row"))

# 5) professor overrides the grade with a custom score
if assess_ok:
    review_assessment(aid, PROF, action="overridden", final_total=1)
    with SessionLocal() as db:
        a2 = db.get(Assessment, aid)
    check("grade overridden via FSM",
          a2.status == "overridden" and a2.final_total == 1)

# 6) audit trail recorded every step
with SessionLocal() as db:
    actors = [row.actor for row in db.query(AuditLog).order_by(AuditLog.id).all()]
check("audit trail has AI + professor actors",
      any(x.startswith("ollama:") for x in actors) and "professor" in actors,
      ", ".join(sorted(set(actors))))

print("\n" + ("ALL SMOKE TESTS PASSED" if all(results) else "SOME CHECKS FAILED"),
      flush=True)

