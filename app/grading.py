"""Deterministic grading — no LLM, pure logic engine."""

from __future__ import annotations

from . import proplog


def _parse_01(text: str) -> int:
    t = text.strip().lower()
    if t in ("0", "f", "false", "no"):
        return 0
    if t in ("1", "t", "true", "yes"):
        return 1
    raise ValueError("expected 0 or 1 (got %r)" % text.strip())


def _parse_yesno(text: str) -> bool:
    t = text.strip().lower()
    if t in ("y", "yes", "true", "t", "1", "tautology", "equivalent"):
        return True
    if t in ("n", "no", "false", "f", "0", "not", "contradiction", "not equivalent"):
        return False
    raise ValueError("expected yes/no (got %r)" % text.strip())


def grade(item, answer_text: str) -> tuple[bool, str]:
    """Return (is_correct, expected_display). Raises ValueError on bad input."""
    if item is None:
        raise ValueError("unknown question")
    p = item.payload
    t = item.type
    if t == "logic_eval":
        expected = proplog.evaluate(p["formula"], p["assignment"])
        return _parse_01(answer_text) == expected, str(expected)
    if t == "tautology_check":
        expected = proplog.is_tautology(p["formula"])
        return _parse_yesno(answer_text) == expected, ("Yes" if expected else "No")
    if t == "equivalence_check":
        expected = proplog.are_equivalent(p["formula1"], p["formula2"])
        return _parse_yesno(answer_text) == expected, ("Equivalent" if expected else "Not equivalent")
    if t == "mcq":
        try:
            idx = int(str(answer_text).strip())
        except (ValueError, TypeError):
            raise ValueError("expected option index 0..%d" % (len(p["options"]) - 1))
        if not 0 <= idx < len(p["options"]):
            raise ValueError("option index out of range")
        expected = p["answer_index"]
        return idx == expected, p["options"][expected]
    raise ValueError(f"unknown item type {t!r}")
