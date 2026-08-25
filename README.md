# Adaptive Tutor — Logic & Set Theory

Lean adaptive tutor with deterministic grading and LLM-assisted hint drafting (human-in-the-loop).

## Stack
- **FastAPI** + **SQLAlchemy 2.0** (`app.db` via `DATABASE_URL`) + **Jinja2**
- **Hand-written propositional logic engine** (`app/proplog.py`) with AST `lru_cache`
- **Adaptive policy** (`app/adaptive.py`) — EMA mastery `K=0.25`, weakest-first, difficulty gate `1→2→3`
- **Local LLM** (`OllamaProvider`) for hint drafts only — `OLLAMA_MODEL`/`OLLAMA_BASE`/`OLLAMA_TIMEOUT` env

## Quick start
```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload   # auto-seeds app.db (46 items) on first run
# http://127.0.0.1:8000/?sid=alice
# professor console: /review  key=professor (set PROFESSOR_KEY env for prod)
```

Env overrides:
```powershell
$env:DATABASE_URL="sqlite:///app.db"
$env:PROFESSOR_KEY="strong-secret"
$env:OLLAMA_MODEL="qwen3.5:4b"; $env:OLLAMA_BASE="http://localhost:11434"
```

## Project layout
```
app/
  main.py      — routes (quiz/answer/dashboard/review/health), auto-seed, cached domain_map
  models.py    — Item / Attempt / HintDraft / AuditLog
  db.py        — engine (DATABASE_URL) + SessionLocal
  proplog.py   — parse/evaluate/is_tautology/are_equivalent (lru_cache)
  grading.py   — deterministic grade()
  adaptive.py  — init/update/select/explain/should_stop
  llm.py       — OllamaProvider (Session pooling, OLLAMA_* env)
  approval.py  — hint_transition FSM
  templates/   — quiz / result / dashboard / done / review
data/
  items.json (46 deterministic), domain_map.json (29 concepts)
```

## How it works
1. `GET /?sid=alice` → `load_state()` builds mastery EMA from `Attempt`s → `adaptive.select()` picks weakest concept within `difficulty_cap()` → approved `HintDraft` injected.
2. `POST /answer/{id}` → `grading.grade()` via `proplog` → `Attempt(correct)` + `AuditLog` agnostic.
3. Professor at `/review` drafts hint via `OllamaProvider.draft_hint()` → `HintDraft(status=draft)` → approve/reject → visible to learners.

No free-text rubric grading — keeps the core honest and fully deterministic; LLM is advisory only.

## Health & audit
- `GET /health` → `{"status":"ok"}`
- `audit_log` records `hint_drafted` / `hint_approved` / `hint_rejected` / `provider_down` with actor/target/detail.

## Demo
See `DEMO_SCRIPT.md` (≈5 min).
