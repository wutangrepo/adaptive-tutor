"""Single-criterion rubric for agreement measurement — does LLM match the engine?

Keeps main.py lean: this is eval-only, not production.
"""

RUBRIC = [
    {"criterion": "the submitted answer is correct for the question", "points": 1},
]

# Prompt used for LLM grading (no answer key given — LLM must reason)
PROMPT_TEMPLATE = """You are grading a logic/set-theory answer. Award 1 if the student's answer is correct, 0 if incorrect.

Question:
{stem}

Type: {qtype}
{extra}

Student answer:
{answer}

Reply with ONLY a JSON object: {{"awarded": 0}} or {{"awarded": 1}} where 1 means correct, 0 means incorrect. No extra text.
"""

def build_prompt(item: dict, student_answer: str) -> str:
    extra = ""
    p = item["payload"]
    if item["type"] == "mcq":
        opts = "\n".join(f"  {i}: {o}" for i, o in enumerate(p["options"]))
        extra = f"Options:\n{opts}"
    elif item["type"] == "logic_eval":
        extra = f"Formula: {p['formula']}\nAssignment: {p['assignment']}"
    elif item["type"] == "tautology_check":
        extra = f"Formula: {p['formula']}"
    elif item["type"] == "equivalence_check":
        extra = f"Formula1: {p['formula1']}\nFormula2: {p['formula2']}"
    return PROMPT_TEMPLATE.format(stem=item["stem"], qtype=item["type"], extra=extra, answer=student_answer)
