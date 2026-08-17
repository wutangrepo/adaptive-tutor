import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates

from . import adaptive, grading
from .db import Base, SessionLocal, engine
from .models import Attempt, Item

DATA = Path(__file__).resolve().parent.parent / "data"

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
def quiz(request: Request, sid: str = "demo", mode: str = "adaptive"):
    st = load_state(sid)
    if mode == "adaptive" and adaptive.should_stop(st.mastery, st.n, cap=len(st.items)):
        return templates.TemplateResponse(request, "done.html", {"sid": sid, "n": st.n})
    if mode == "adaptive":
        item, p = adaptive.select(st.items, st.mastery, st.prereqs, st.seen)
        why = adaptive.explain(item, st.mastery, st.prereqs)
    else:
        item = st.items[st.n % len(st.items)]
        why = "fixed order (demo fallback)"
    return templates.TemplateResponse(request, "quiz.html",
                                      {"item": item, "why": why, "sid": sid, "n": st.n,
                                       "concept_mastery": st.mastery})


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
    return templates.TemplateResponse(request, "result.html",
                                      {"item": item, "correct": ok, "expected": expected,
                                       "error": error, "sid": sid})


@app.get("/dashboard")
def dashboard(request: Request, sid: str = "demo"):
    st = load_state(sid)
    rows = sorted(st.mastery.items(), key=lambda kv: kv[1])
    return templates.TemplateResponse(request, "dashboard.html", {"sid": sid, "rows": rows})