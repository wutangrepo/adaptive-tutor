# LLM provider layer: talks to a local Ollama server and turns its free-text
# output into *validated* structured drafts.  Nothing here touches the database
# or decides approval state -- callers (main.py) own that.  Two rules shape
# this module:
#   1. The model's raw text is never trusted: every grade passes through
#      validate_grade() before it can reach an Assessment.
#   2. Any failure (server down, bad JSON, rule violation) raises instead of
#      returning a plausible-looking partial result.

import json
import re

import requests


class ProviderDown(Exception):
    pass


class BadGrade(Exception):
    pass


def _extract_json(raw: str):
    """Pull the first JSON object out of model output.

    Small models routinely wrap JSON in prose or ```json fences; find the
    first balanced {...} block and parse that, else raise BadGrade.
    """
    text = re.sub(r"```(?:json)?", "", raw)
    start = text.find("{")
    if start == -1:
        raise BadGrade("no JSON object in model output")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError as e:
                    raise BadGrade(f"invalid JSON: {e}") from e
    raise BadGrade("unbalanced JSON in model output")


class OllamaProvider:
    def __init__(self, model="qwen3.5:4b", base="http://localhost:11434"):
        self.model = model
        self.base = base.rstrip("/")

    @property
    def name(self) -> str:
        # Matches the actor format used in AuditLog rows ("ollama:qwen3.5:4b").
        return f"ollama:{self.model}"

    def complete(self, prompt: str) -> str:
        try:
            response = requests.post(
                f"{self.base}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60
            )
            response.raise_for_status()  # requests does not raise for bad HTTP status codes, so we need to do it manually
            return response.json()["response"]
        except Exception as e:
            raise ProviderDown(str(e))

    def validate_grade(self, raw: str, rubric: list) -> dict:
        """Parse and validate a model draft against the rubric.

        Returns {criteria: [{criterion, awarded, points}], total, max,
        confidence}.  Awarding is all-or-nothing per criterion -- a small
        local model must not invent half points.  Raises BadGrade on any
        deviation, which callers should map to status "needs_human".
        """
        d = _extract_json(raw)
        if not isinstance(d, dict):
            raise BadGrade("grade draft is not an object")
        confidence = d.get("confidence")
        # bool is excluded explicitly: isinstance(True, int) is True in Python,
        # so "confidence": true would otherwise pass the type check (and the
        # range check, since True <= 1.0) and be accepted as confidence = 1.
        if (isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not (0.0 <= confidence <= 1.0)):
            raise BadGrade("confidence must be a number in [0, 1]")
        criteria = d.get("criteria", [])
        if not isinstance(criteria, list) or len(criteria) != len(rubric):
            raise BadGrade(f"expected {len(rubric)} criteria, got {len(criteria)}")
        total = 0
        checked = []
        for got, spec in zip(criteria, rubric):
            awarded = got.get("awarded") if isinstance(got, dict) else None
            # Tolerate integral floats ("awarded": 2.0 == 2) but reject
            # fractional ones (1.5 -- the all-or-nothing policy allows no half
            # points), strings ("2"), bools (True == 1) and anything else.
            if isinstance(awarded, float) and awarded.is_integer():
                awarded = int(awarded)
            if not isinstance(awarded, int) or isinstance(awarded, bool):
                raise BadGrade("awarded must be an integer")
            if awarded not in (0, spec["points"]):
                raise BadGrade("awarded must be 0 or full points")
            total += awarded
            checked.append({
                "criterion": spec["criterion"],
                "awarded": awarded,
                "points": spec["points"],
            })
        d["criteria"], d["total"] = checked, total
        d["max"] = sum(s["points"] for s in rubric)
        return d

    def draft_grade(self, question: str, answer: str, rubric: list) -> dict:
        """Ask the model to grade `answer` against `rubric`; returns validated dict."""
        rubric_text = "\n".join(
            f"- {s['criterion']} ({s['points']} pts)" for s in rubric
        )
        prompt = (
            "You are grading a student answer. Grade strictly against the "
            "rubric. Award either 0 or the full points for each criterion.\n\n"
            f"Question:\n{question}\n\n"
            f"Student answer:\n{answer}\n\n"
            f"Rubric:\n{rubric_text}\n\n"
            'Reply with ONLY a JSON object: {"criteria": [{"criterion": "...", '
            '"awarded": 0}], "confidence": 0.0} where awarded is 0 or the '
            "criterion's full points and confidence is your certainty from 0 to 1."
        )
        return self.validate_grade(self.complete(prompt), rubric)

    def draft_hint(self, question: str) -> str:
        """Draft one hint for `question`.  Returns plain text; always goes to
        HintDraft for professor approval before a learner ever sees it."""
        prompt = (
            "Write ONE short hint (max 2 sentences) for this logic question. "
            "Nudge the student toward the right idea — never give the final "
            "answer.\n\n"
            f"Question:\n{question}\n\n"
            "Reply with only the hint text."
        )
        return self.complete(prompt).strip()
