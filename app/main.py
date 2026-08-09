from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates

from .db import engine, SessionLocal, Base
from .models import Item
from . import grading

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Adaptive Tutor — walking skeleton")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def get_items():
    with SessionLocal() as db:
        return db.query(Item).order_by(Item.id).all()


@app.get("/")
def quiz(request: Request, idx: int = 0):
    items = get_items()
    if idx >= len(items):
        return templates.TemplateResponse(request, "done.html")
    return templates.TemplateResponse(request, "quiz.html", {
        "item": items[idx], "idx": idx, "total": len(items)})


@app.post("/answer/{idx}")
async def answer(idx: int, request: Request, student_answer: str = Form(...)):
    items = get_items()
    item = items[idx]
    try:
        ok, expected = grading.grade(item, student_answer)
        error = None
    except ValueError as e:
        ok, expected, error = None, None, str(e)
    return templates.TemplateResponse(request, "result.html", {
        "item": item, "correct": ok, "expected": expected,
        "error": error, "next": idx + 1})