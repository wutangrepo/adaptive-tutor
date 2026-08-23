"""Professor/student separation tests (Option A shared key + cookie)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main as main
from app.db import Base
from app.models import Assessment, HintDraft, Item


class StubProvider:
    """Deterministic stand-in so tests never touch Ollama."""
    name = "stub"

    def complete(self, prompt: str) -> str:
        if "hint" in prompt.lower():
            return "Think about what A AND B being true implies."
        return ('{"criteria": [{"awarded": 2}, {"awarded": 1}], '
                '"confidence": 0.9}')

    def draft_hint(self, question: str) -> str:
        return "Think about what A AND B being true implies."

    def draft_grade(self, question: str, answer: str, rubric: list) -> dict:
        return self.validate_grade(self.complete(""), rubric)

    def validate_grade(self, raw: str, rubric: list) -> dict:
        from app.llm import _extract_json
        return _extract_json(raw)


@pytest.fixture()
def client(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine)
    monkeypatch.setattr(main, "SessionLocal", S)
    monkeypatch.setattr(main, "PROFESSOR_KEY", "test-key")
    monkeypatch.setattr(main, "llm_provider", StubProvider())
    with S() as db:
        db.add(Item(id="t1", type="mcq", concepts=[], difficulty=1,
                    stem="stub question",
                    payload={"options": ["a", "b"], "answer_index": 0}))
        db.commit()
    return TestClient(main.app)


def test_review_hides_console_from_students(client):
    r = client.get("/review")
    assert r.status_code == 200
    assert "professor key" in r.text          # login form shown
    assert "Grade drafts" not in r.text       # console hidden


def test_wrong_key_denied(client):
    r = client.post("/review/login", data={"key": "letmein"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert not client.cookies.get(main.COOKIE_NAME)


def test_correct_key_grants_access(client):
    r = client.post("/review/login", data={"key": "test-key"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert client.cookies.get(main.COOKIE_NAME)
    page = client.get("/review")
    assert "Grade drafts" in page.text
    assert "Log out" in page.text


def test_student_cannot_approve_assessment(client):
    # seed a pending assessment directly
    with main.SessionLocal() as db:
        db.add(Assessment(item_id="t1", learner_id="sneaky", answer="x",
                          status="pending", ai_total=3, ai_max=3,
                          ai_confidence=0.9))
        db.commit()
        aid = db.query(Assessment).first().id

    r = client.post(f"/review/assessment/{aid}", data={"action": "approved"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "login+required" in r.headers["location"]
    with main.SessionLocal() as db:
        assert db.get(Assessment, aid).status == "pending"   # untouched


def test_student_cannot_draft_hints(client):
    client.post("/hints/draft/t1")            # no cookie -> blocked
    with main.SessionLocal() as db:
        assert db.query(HintDraft).count() == 0


def test_professor_can_draft_hint_after_login(client):
    client.post("/review/login", data={"key": "test-key"})
    r = client.post("/review/draft-hint", data={"item_id": "t1"},
                    follow_redirects=True)
    assert r.status_code == 200
    with main.SessionLocal() as db:
        drafts = db.query(HintDraft).all()
    assert len(drafts) == 1 and drafts[0].status == "draft"
    assert "A AND B" in drafts[0].text


def test_logout_revokes_access(client):
    client.post("/review/login", data={"key": "test-key"})
    client.post("/review/logout")
    page = client.get("/review")
    assert "professor key" in page.text