import hashlib
import hmac
import json
import logging
import os
import warnings
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import adaptive, approval, grading, llm
from .db import SessionLocal
from .models import Attempt, AuditLog, HintDraft, Item
from .seed import ensure_db

DATA = Path(__file__).resolve().parent.parent / "data"
log = logging.getLogger(__name__)

# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
PROFESSOR_KEY = os.environ.get("PROFESSOR_KEY", "professor")
if PROFESSOR_KEY == "professor":
    warnings.warn("PROFESSOR_KEY is default 'professor' — set env var for non-demo use", UserWarning)

COOKIE_NAME = "professor_token"
llm_provider = llm.OllamaProvider()  # reads OLLAMA_* env vars


def _professor_token() -> str:
    """Cookie value derived from key; changing key voids all sessions."""
    return hmac.new(PROFESSOR_KEY.encode(), b"professor-session", hashlib.sha256).hexdigest()


def _is_professor(request: Request) -> bool:
    expected = _professor_token()
    got = request.cookies.get(COOKIE_NAME, "")
    return hmac.compare_digest(expected, got)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------------------------------------------------
# App + lifespan (replaces deprecated @app.on_event)
# ------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_db()
    yield


app = FastAPI(title="Adaptive Tutor", version="2.2", lifespan=lifespan)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Fallback for TestClient without lifespan context + `python -m app.main` bare import
ensure_db()


@lru_cache(maxsize=1)
def _domain_cache():
    dm = json.loads((DATA / "domain_map.json").read_text(encoding="utf-8"))
    prereqs = {c["id"]: c["prereqs"] for c in dm["concepts"]}
    concepts = set(prereqs)
    return dm, prereqs, concepts


def load_state(sid: str, db: Session | None = None):
    # Reuse passed session when possible to avoid double open
    close_after = False
    if db is None:
        db = SessionLocal()
        close_after = True
    try:
        items = db.query(Item).order_by(Item.id).all()
        attempts = db.query(Attempt).filter_by(learner_id=sid).order_by(Attempt.id).all()
    finally:
        if close_after:
            db.close()

    _, prereqs, base_concepts = _domain_cache()
    concepts = set(base_concepts)
    for it in items:
        concepts.update(it.concepts)  # type: ignore[arg-type]
    by_id = {it.id: it for it in items}
    mastery = adaptive.init_mastery(sorted(concepts))
    for a in attempts:
        # Guard against stale attempt referencing deleted item
        it = by_id.get(a.item_id)
        if it is None:
            continue
        mastery = adaptive.update(mastery, it.concepts, bool(a.correct))
    return SimpleNamespace(items=items, mastery=mastery, prereqs=prereqs, seen={a.item_id for a in attempts}, n=len(attempts))


# ------------------------------------------------------------
# Student routes
# ------------------------------------------------------------
@app.get("/")
def quiz(request: Request, sid: str = "demo", mode: str = "adaptive", msg: str = "", db: Session = Depends(get_db)):
    st = load_state(sid, db)
    if mode == "adaptive" and adaptive.should_stop(st.mastery, st.n, cap=len(st.items)):
        return templates.TemplateResponse(request, "done.html", {"sid": sid, "n": st.n})
    if mode == "adaptive":
        item = adaptive.select(st.items, st.mastery, st.prereqs, st.seen)
        why = adaptive.explain(item, st.mastery, st.prereqs)
    else:
        item = st.items[st.n % len(st.items)]
        why = "fixed order (demo fallback)"
    hint_row = db.query(HintDraft).filter_by(item_id=item.id, status="approved").order_by(HintDraft.id.desc()).first()
    hint = hint_row.text if hint_row else None
    return templates.TemplateResponse(
        request, "quiz.html", {"item": item, "why": why, "sid": sid, "n": st.n, "concept_mastery": st.mastery, "hint": hint, "msg": msg}
    )


@app.post("/answer/{item_id}")
def answer(request: Request, item_id: str, sid: str = "demo", student_answer: str = Form(...), db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        return templates.TemplateResponse(
            request, "result.html", {"item": None, "correct": None, "expected": None, "error": "unknown question", "sid": sid, "student_answer": student_answer}
        )
    try:
        ok, expected = grading.grade(item, student_answer)
        error = None
    except ValueError as e:
        ok, expected, error = None, None, str(e)
    if ok is not None:
        db.add(Attempt(learner_id=sid, item_id=item_id, correct=int(ok)))
        db.commit()
    # MCQ submits index; show option text
    answer_display = student_answer
    if item.type == "mcq":
        try:
            answer_display = item.payload["options"][int(student_answer)]
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    return templates.TemplateResponse(
        request, "result.html", {"item": item, "correct": ok, "expected": expected, "error": error, "sid": sid, "student_answer": answer_display}
    )


@app.get("/dashboard")
def dashboard(request: Request, sid: str = "demo", db: Session = Depends(get_db)):
    st = load_state(sid, db)
    rows = sorted(st.mastery.items(), key=lambda kv: kv[1])
    return templates.TemplateResponse(request, "dashboard.html", {"sid": sid, "rows": rows})


@app.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------------
# Professor / HITL — Hints only
# ------------------------------------------------------------
def _audit(db: Session, actor: str, action: str, target: str, detail=None):
    db.add(AuditLog(actor=actor, action=action, target=target, detail=detail))


@app.get("/review")
def review(request: Request, msg: str = "", db: Session = Depends(get_db)):
    authorized = _is_professor(request)
    hints: list = []
    items: list = []
    attempts: list = []
    if authorized:
        hints = db.query(HintDraft, Item).join(Item, HintDraft.item_id == Item.id).filter(HintDraft.status == "draft").order_by(HintDraft.id.desc()).all()
        attempts = db.query(Attempt, Item).join(Item, Attempt.item_id == Item.id).order_by(Attempt.id.desc()).limit(20).all()
        items = db.query(Item).order_by(Item.id).all()
    return templates.TemplateResponse(request, "review.html", {"authorized": authorized, "hints": hints, "items": items, "recent_attempts": attempts, "msg": msg})


@app.post("/review/login")
def review_login(key: str = Form("")):
    if hmac.compare_digest(key.strip(), PROFESSOR_KEY):
        resp = RedirectResponse("/review", status_code=303)
        resp.set_cookie(COOKIE_NAME, _professor_token(), httponly=True, samesite="lax")
        return resp
    return RedirectResponse("/review?msg=wrong+key", status_code=303)


@app.post("/review/logout")
def review_logout():
    resp = RedirectResponse("/review", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@app.post("/hints/draft/{item_id}")
def hint_draft(item_id: str, request: Request, db: Session = Depends(get_db)):
    """Draft a hint (professor-only) → status='draft'."""
    if not _is_professor(request):
        return RedirectResponse("/review?msg=professor+login+required", status_code=303)
    item = db.get(Item, item_id)
    if item is None:
        return RedirectResponse("/review?msg=unknown+item", status_code=303)
    try:
        text = llm_provider.draft_hint(item.stem)
    except llm.ProviderDown as e:
        _audit(db, "system", "provider_down", item_id, {"error": str(e)})
        db.commit()
        return RedirectResponse("/review?msg=AI+provider+unavailable", status_code=303)
    db.add(HintDraft(item_id=item_id, text=text, status="draft"))
    _audit(db, llm_provider.name, "hint_drafted", item_id, {"text": text[:200]})
    db.commit()
    return RedirectResponse("/review?msg=hint+drafted", status_code=303)


@app.post("/review/hint/{hint_id}")
def review_hint(hint_id: int, request: Request, action: str = Form(...), db: Session = Depends(get_db)):
    if not _is_professor(request):
        return RedirectResponse("/review?msg=professor+login+required", status_code=303)
    h = db.get(HintDraft, hint_id)
    if h is None:
        return RedirectResponse("/review?msg=no+such+hint", status_code=303)
    try:
        new_status = approval.hint_transition(h.status, action)
    except ValueError:
        return RedirectResponse(f"/review?msg={quote(f'illegal move {h.status!r} -> {action!r}')}", status_code=303)
    h.status = new_status
    _audit(db, "professor", f"hint_{new_status}", f"hint:{h.id}")
    db.commit()
    return RedirectResponse(f"/review?msg=hint+{new_status}", status_code=303)


@app.post("/review/draft-hint")
def review_draft_hint(request: Request, item_id: str = Form(...), db: Session = Depends(get_db)):
    return hint_draft(item_id, request, db)
