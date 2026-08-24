import hashlib
import hmac
import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import adaptive, approval, grading, llm
from .db import Base, SessionLocal, engine
from .models import Attempt, Item, Assessment, AuditLog, HintDraft

DATA = Path(__file__).resolve().parent.parent / "data"

# AI drafts at or above this confidence wait in "pending"; below it they are
# flagged "needs_human" before a professor ever sees them.
CONFIDENCE_GATE = 0.6

llm_provider = llm.OllamaProvider()

# ---------------------------------------------------------------------------
# Professor access control (Option A: shared key + signed cookie).
# One dependency-style check (_is_professor) guards every professor route, so
# swapping in real user accounts later touches exactly this block.
# Set PROFESSOR_KEY in the environment for anything beyond a demo.
# ---------------------------------------------------------------------------
PROFESSOR_KEY = os.environ.get("PROFESSOR_KEY", "professor")
COOKIE_NAME = "professor_token"


def _professor_token() -> str:
    """Cookie value derived from the key; changing the key voids all sessions."""
    return hmac.new(PROFESSOR_KEY.encode(), b"professor-session",
                    hashlib.sha256).hexdigest()


def _is_professor(request: Request) -> bool:
    expected = _professor_token()
    got = request.cookies.get(COOKIE_NAME, "")
    return hmac.compare_digest(expected, got)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Adaptive Tutor — W2")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def load_state(sid: str):
    with SessionLocal() as db:
        items = db.query(Item).order_by(Item.id).all()
        attempts = (db.query(Attempt).filter_by(learner_id=sid)
                    .order_by(Attempt.id).all())
    dm = json.loads((DATA / "domain_map.json").read_text(encoding="utf-8"))
    prereqs = {c["id"]: c["prereqs"] for c in dm["concepts"]}
    concepts = set(prereqs)
    for it in items:
        concepts.update(it.concepts)  # type: ignore[arg-type]  # it is a list；Pylance only sees Column
    by_id = {it.id: it for it in items}
    mastery = adaptive.init_mastery(sorted(concepts))
    for a in attempts:
        mastery = adaptive.update(mastery, by_id[a.item_id].concepts, bool(a.correct))
    return SimpleNamespace(items=items, mastery=mastery, prereqs=prereqs,
                           seen={a.item_id for a in attempts}, n=len(attempts))


@app.get("/")
def quiz(request: Request, sid: str = "demo", mode: str = "adaptive",
         msg: str = ""):
    st = load_state(sid)
    if mode == "adaptive" and adaptive.should_stop(st.mastery, st.n, cap=len(st.items)):
        return templates.TemplateResponse(request, "done.html", {"sid": sid, "n": st.n})
    if mode == "adaptive":
        item, p = adaptive.select(st.items, st.mastery, st.prereqs, st.seen)
        why = adaptive.explain(item, st.mastery, st.prereqs)
    else:
        item = st.items[st.n % len(st.items)]
        why = "fixed order (demo fallback)"
    with SessionLocal() as db:
        hint_row = (db.query(HintDraft)
                    .filter_by(item_id=item.id, status="approved")
                    .order_by(HintDraft.id.desc()).first())
    hint = hint_row.text if hint_row else None
    return templates.TemplateResponse(request, "quiz.html",
                                      {"item": item, "why": why, "sid": sid, "n": st.n,
                                       "concept_mastery": st.mastery, "hint": hint,
                                       "msg": msg})


@app.post("/answer/{item_id}")
async def answer(request: Request, item_id: str, sid: str = "demo",
                 student_answer: str = Form(...)):
    with SessionLocal() as db:
        item = db.get(Item, item_id)
    try:
        ok, expected = grading.grade(item, student_answer)
        error = None
    except ValueError as e:
        ok, expected, error = None, None, str(e)
    if ok is not None:
        with SessionLocal() as db:
            db.add(Attempt(learner_id=sid, item_id=item_id, correct=int(ok)))
            db.commit()
    # MCQ forms submit the option *index*; resolve it to the option text so
    # students (and the AI grader) see "A ∧ ¬B", not "1".
    answer_display = student_answer
    if item is not None and item.type == "mcq":
        try:
            answer_display = item.payload["options"][int(student_answer)]
        except (KeyError, ValueError, IndexError):
            pass
    return templates.TemplateResponse(request, "result.html",
                                      {"item": item, "correct": ok, "expected": expected,
                                       "error": error, "sid": sid,
                                       "student_answer": answer_display})


@app.get("/dashboard")
def dashboard(request: Request, sid: str = "demo"):
    st = load_state(sid)
    rows = sorted(st.mastery.items(), key=lambda kv: kv[1])
    return templates.TemplateResponse(request, "dashboard.html", {"sid": sid, "rows": rows})


# --------------------------------------------------------------------------
# Human-in-the-loop AI workflows.  The LLM only ever produces *drafts*
# (Assessment / HintDraft rows); nothing reaches a learner until a professor
# moves it through approval.py's state machines.
# --------------------------------------------------------------------------

def rubric_for(item):
    """Rubric for reasoning feedback.

    The answer itself is already graded deterministically -- the AI only
    assesses the *explanation*: is it sound, and does it engage the concept?
    """
    return [
        {"criterion": f"the reasoning is logically sound for this question: "
                      f"{item.stem[:100]}", "points": 2},
        {"criterion": "the reasoning cites the relevant rule or concept",
         "points": 1},
    ]


def _audit(db, actor, action, target, detail=None):
    db.add(AuditLog(actor=actor, action=action, target=target, detail=detail))


@app.get("/review")
def review(request: Request, msg: str = ""):
    authorized = _is_professor(request)
    assessments, hints, items, attempts = [], [], [], []
    if authorized:
        with SessionLocal() as db:
            assessments = (db.query(Assessment, Item)
                           .join(Item, Assessment.item_id == Item.id)
                           .filter(Assessment.status.in_(("pending", "needs_human")))
                           .order_by(Assessment.id.desc()).all())
            hints = (db.query(HintDraft, Item)
                     .join(Item, HintDraft.item_id == Item.id)
                     .filter(HintDraft.status == "draft")
                     .order_by(HintDraft.id.desc()).all())
            attempts = (db.query(Attempt, Item)
                        .join(Item, Attempt.item_id == Item.id)
                        .order_by(Attempt.id.desc()).limit(20).all())
            items = db.query(Item).order_by(Item.id).all()
    return templates.TemplateResponse(request, "review.html", {
        "authorized": authorized,
        "assessments": assessments, "hints": hints, "items": items,
        "recent_attempts": attempts,
        "msg": msg, "gate": CONFIDENCE_GATE})


@app.post("/review/login")
def review_login(request: Request, key: str = Form("")):
    if hmac.compare_digest(key.strip(), PROFESSOR_KEY):
        resp = RedirectResponse("/review", status_code=303)
        resp.set_cookie(COOKIE_NAME, _professor_token(), httponly=True,
                        samesite="lax")
        return resp
    return RedirectResponse("/review?msg=wrong+key", status_code=303)


@app.post("/review/logout")
def review_logout():
    resp = RedirectResponse("/review", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@app.post("/assess/{item_id}")
async def assess_draft(item_id: str, sid: str = Form("demo"),
                       answer_text: str = Form(...),
                       picked_answer: str = Form("")):
    """Draft an AI grade for a free-text answer; low confidence => needs_human."""
    with SessionLocal() as db:
        item = db.get(Item, item_id)
    if item is None:
        return RedirectResponse(f"/?sid={sid}&msg=unknown+item", status_code=303)
    if picked_answer:
        # Give the model the student's concrete choice as grading context.
        answer_text = f"[student's selected answer: {picked_answer}] {answer_text}"
    breakdown, total, max_pts, confidence = None, None, None, None
    status = "needs_human"
    note = ""
    try:
        d = llm_provider.draft_grade(item.stem, answer_text, rubric_for(item))
        breakdown, total, max_pts = d["criteria"], d["total"], d["max"]
        confidence = d["confidence"]
        status = "pending" if confidence >= CONFIDENCE_GATE else "needs_human"
        note = (f"AI feedback drafted ({status}, {total}/{max_pts}) - "
                f"the professor will review it")
    except llm.BadGrade as e:
        # The model broke the rules -- keep the submission, flag it for a human.
        breakdown = {"error": str(e)}
        note = "AI draft was malformed - sent to the professor for manual grading"
    except llm.ProviderDown as e:
        with SessionLocal() as db:
            _audit(db, "system", "provider_down", item_id, {"error": str(e)})
            db.commit()
        return RedirectResponse(f"/?sid={sid}&msg=AI+tutor+unavailable+right+now",
                                status_code=303)
    with SessionLocal() as db:
        db.add(Assessment(item_id=item_id, learner_id=sid, answer=answer_text,
                          status=status, ai_breakdown=breakdown, ai_total=total,
                          ai_max=max_pts, ai_confidence=confidence))
        _audit(db, llm_provider.name, "grade_drafted", item_id,
               {"status": status, "total": total, "confidence": confidence})
        db.commit()
    return RedirectResponse(f"/?sid={sid}&msg={quote(note)}", status_code=303)


@app.post("/hints/draft/{item_id}")
def hint_draft(item_id: str, request: Request):
    """Draft a hint for an item; professor-only; lands as 'draft' pending approval."""
    if not _is_professor(request):
        return RedirectResponse("/review?msg=professor+login+required",
                                status_code=303)
    with SessionLocal() as db:
        item = db.get(Item, item_id)
    if item is None:
        return RedirectResponse("/review?msg=unknown+item", status_code=303)
    try:
        text = llm_provider.draft_hint(item.stem)
    except llm.ProviderDown as e:
        with SessionLocal() as db:
            _audit(db, "system", "provider_down", item_id, {"error": str(e)})
            db.commit()
        return RedirectResponse("/review?msg=AI+provider+unavailable", status_code=303)
    with SessionLocal() as db:
        db.add(HintDraft(item_id=item_id, text=text, status="draft"))
        _audit(db, llm_provider.name, "hint_drafted", item_id, {"text": text[:200]})
        db.commit()
    return RedirectResponse("/review?msg=hint+drafted", status_code=303)


@app.post("/review/assessment/{assessment_id}")
def review_assessment(assessment_id: int, request: Request,
                      action: str = Form(...),
                      final_total: int | None = Form(None)):
    """Professor decision on an AI-drafted grade (approved / overridden)."""
    if not _is_professor(request):
        return RedirectResponse("/review?msg=professor+login+required",
                                status_code=303)
    with SessionLocal() as db:
        a = db.get(Assessment, assessment_id)
        if a is None:
            return RedirectResponse("/review?msg=no+such+assessment", status_code=303)
        try:
            new_status = approval.assessment_transition(a.status, action)
        except ValueError:
            return RedirectResponse(
                f"/review?msg={quote(f'illegal move {a.status!r} -> {action!r}')}",
                status_code=303)
        a.status = new_status
        a.final_total = final_total if final_total is not None else a.ai_total
        _audit(db, "professor", new_status, f"assessment:{a.id}",
               {"final_total": a.final_total})
        db.commit()
    return RedirectResponse(f"/review?msg=assessment+{new_status}", status_code=303)


@app.post("/review/hint/{hint_id}")
def review_hint(hint_id: int, request: Request, action: str = Form(...)):
    """Professor decision on a draft hint (approved / rejected)."""
    if not _is_professor(request):
        return RedirectResponse("/review?msg=professor+login+required",
                                status_code=303)
    with SessionLocal() as db:
        h = db.get(HintDraft, hint_id)
        if h is None:
            return RedirectResponse("/review?msg=no+such+hint", status_code=303)
        try:
            new_status = approval.hint_transition(h.status, action)
        except ValueError:
            return RedirectResponse(
                f"/review?msg={quote(f'illegal move {h.status!r} -> {action!r}')}",
                status_code=303)
        h.status = new_status
        _audit(db, "professor", f"hint_{new_status}", f"hint:{h.id}")
        db.commit()
    return RedirectResponse(f"/review?msg=hint+{new_status}", status_code=303)


@app.post("/review/draft-hint")
def review_draft_hint(request: Request, item_id: str = Form(...)):
    """Professor console entry point for AI hint drafting."""
    return hint_draft(item_id, request)