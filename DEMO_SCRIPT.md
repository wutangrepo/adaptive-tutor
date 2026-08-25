# Demo Script — Adaptive Tutor (≈5 min)

## Before the demo
```powershell
cd C:\Users\Mcius\Desktop\adaptive-tutor
.\.venv\Scripts\Activate.ps1
# Start app (auto-seeds app.db on first run):
uvicorn app.main:app --reload
# Open two windows:
# Student:  http://127.0.0.1:8000/?sid=alice
# Professor: http://127.0.0.1:8000/review  (key: professor)
# Env overrides:
# $env:OLLAMA_MODEL="qwen3.5:4b"; $env:OLLAMA_BASE="http://localhost:11434"
```

## 1. Pitch (30s)
> Adaptive tutor for Logic & Set Theory. Picks next question by your weakest concept, gates difficulty by best mastery, and uses a local LLM to *draft hints* — **nothing reaches students without professor approval**. Everything is audited.

## 2. Student loop (2 min)
- **Why this question?** panel explains targeting + difficulty tier.
- Answer → instant deterministic grading (real propositional engine, not LLM).
- Mastery bars update (EMA `K=0.25`).
- Wrong answer → re-drills weakest concept, doesn't hide topic.
- **Dashboard** shows heatmap + progress bars.

## 3. Professor console (2 min)
- Login with professor key (`PROFESSOR_KEY` env). Students cannot see this.
- **Recent learner answers** live table.
- **Draft a hint**: pick question → *Ask AI* → hint lands as `draft`.
- Approve/Reject → approved hints appear to learners on that question; rejected never do.
- Every hint draft/approval is in `audit_log`.

## 4. Close loop (30s)
- Student hits same question → approved hint visible. Rejected ones absent.
- After 9 questions or all concepts ≥0.75 → done. Restart keeps mastery and re-adapts.

## Under the hood
- FastAPI + SQLAlchemy (file `app.db`, `DATABASE_URL` override) + Jinja2
- Hand-written logic engine (`app/proplog.py:12` cached AST, `lru_cache`) for deterministic grading
- Adaptive policy (`app/adaptive.py:1`) weakest-first + difficulty cap + prereq de-prioritization
- Ollama provider (`app/llm.py:1`) `Session` pooling, env-configurable, `ProviderDown` handled

## Q&A
- **LLM down?** Hint draft fails → `provider_down` audit, core quiz still works offline.
- **Why local model?** No data leaves machine, `OllamaProvider` drop-in for cloud API.
- **Selection?** Mastery EMA per concept, weakest first, caps `1→2→3` at `0.5/0.7`, prereqs never hide pool.
