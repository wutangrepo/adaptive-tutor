# Demo Script — Adaptive Tutor (≈6–8 minutes)

## Before the demo (5-minute checklist)

```powershell
cd C:\Users\Mcius\Desktop\adaptive-tutor
.\.venv\Scripts\Activate.ps1
# 1. Ollama must be running (system tray or:  ollama serve)
# 2. Fresh data (optional but nice):
.\.venv\Scripts\python.exe scripts\seed.py
# 3. Start the app:
uvicorn app.main:app --reload
# 4. Open two browser windows side by side:
#    Student:  http://127.0.0.1:8000/?sid=alice
#    Professor: http://127.0.0.1:8000/review      (key: professor)
```

---

## 1. The pitch (30 s)

> "This is an adaptive tutor for Logic and Set Theory. It picks the next
> question based on what the learner is weakest at, gates difficulty by
> demonstrated mastery, and — the part I want to show you — it uses a local
> LLM to draft grades and hints, but **nothing reaches the student without a
> professor's approval**. Every AI action is written to an audit log."

## 2. The student loop (2 min) — student window

- Point at the **"Why this question?"** panel: *"The tutor explains its choice —
  it's targeting my weakest concept, and it tells me which difficulty tier I've
  earned."*
- Answer a question, submit.
- *"Instant deterministic feedback — logic answers are graded by a real
  propositional-logic engine, not pattern matching."*
- Point at the **mastery bars** under the question: *"Mastery updates after
  every answer — 25% of the gap closes each time."*
- Answer one **wrong on purpose**: *"A wrong answer doesn't hide the topic —
  the tutor re-drills the weakest concept instead."*
- Click **"view mastery dashboard"**: *"Every concept, color-coded. Red is
  where the tutor will take me next."*

## 3. AI feedback on reasoning (1 min) — student window

- After any answer, open **"🧠 Show your reasoning — get AI feedback"**
- *"The answer itself was graded deterministically — a real logic engine, no
  AI needed. But the engine can't judge *why* an answer is right. So the
  student can submit their reasoning, and a local LLM — qwen3.5 running
  offline — assesses how sound the explanation is, criterion by criterion,
  with a confidence score."*
- Type a short reasoning sentence, submit.
- *"Notice where it lands: the **professor's queue**, not the student's
  screen. Low-confidence or malformed drafts are flagged 'needs_human'
  automatically."*

## 4. The professor console (2–3 min) — professor window

- Log in with the professor key. *"Professors and students are strictly
  separated — students can neither see this console nor each other's answers."*
- **Recent learner answers** table: *"Every quiz attempt, live."*
- Find the AI grade draft: *"Per-criterion breakdown, total, confidence.
  I can **approve** it as-is, or **override** with my own score — the AI never
  has the final word."* → click Override, set your own score.
- **Draft a hint**: pick a question, click "Ask AI". *"The hint is also just a
  draft."* → Approve it.
- *"Every step here — AI drafts, approvals, overrides — is written to an
  immutable audit log with who did what."*

## 5. Close the loop (30 s) — student window

- Answer until the approved hint's question appears (or just mention it):
  *"And when the student reaches that question, the approved hint is there —
  the rejected ones never are."*
- *"When the tutor decides you've mastered enough — or after 9 questions —
  it stops, and restarting keeps your mastery and re-adapts."*

## 6. Closing line (20 s)

> "Under the hood: FastAPI + SQLAlchemy, a hand-written propositional-logic
> engine for deterministic grading, a mastery model driving question
> selection, and a local Ollama model behind a strict validation layer —
> the LLM proposes, the professor disposes, and everything is auditable."

---

## Backup answers for likely questions

- **"What if the LLM is down?"** — Every provider failure raises and is logged;
  deterministic grading of the quiz never touches the LLM, so the core tutor
  works offline even with the AI features down.
- **"What if the LLM returns garbage?"** — A validation layer enforces the
  rubric: criteria count must match, scores are all-or-nothing, confidence must
  be in [0,1]. Violations become `needs_human`, never a bad grade.
- **"Why a local model?"** — No data leaves the machine and it's free; the
  provider is a single class, so switching to a cloud API is a drop-in change.
- **"How does question selection work?"** — Mastery per concept, weakest-concept
  first, difficulty gated by the best mastery shown; prerequisites de-prioritize
  but never hide questions.
