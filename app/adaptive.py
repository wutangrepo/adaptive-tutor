"""Adaptive tutoring policy — pure functions, easy to test."""

from __future__ import annotations

PREREQ_OK = 0.50  # prerequisite mastery threshold
GOAL = 0.75  # "mastered" threshold
K = 0.25  # EMA update speed: move 25% toward outcome


def init_mastery(concepts: list[str], value: float = 0.5) -> dict[str, float]:
    return {c: value for c in concepts}


def update(mastery: dict[str, float], concepts: list[str], correct: bool) -> dict[str, float]:
    """Exponential moving average per concept (correct→1.0, wrong→0.0)."""
    out = 1.0 if correct else 0.0
    m = dict(mastery)
    for c in concepts:
        p = m.get(c, 0.5)
        m[c] = round(p + K * (out - p), 3)
    return m


def difficulty_cap(mastery: dict[str, float]) -> int:
    """Highest difficulty tier earned — gated by *best* mastery, not average.

    Prevents a single wrong answer from collapsing the pool to the easiest tier.
    """
    strongest = max(mastery.values()) if mastery else 0.5
    if strongest >= 0.7:
        return 3
    if strongest >= 0.5:
        return 2
    return 1


def select(items, mastery: dict[str, float], prereqs: dict[str, list[str]], seen: set[str]):
    """Pick next item. Deterministic tie-break by (weakness, prereq_shortfall, difficulty, id).

    Priority:
      1) weakest concept first (re-drill gaps)
      2) prefer items whose prerequisites are met
      3) simpler item first within same weakness
    Only items with difficulty <= cap are eligible; falls back gracefully.
    """

    def weakest(it) -> float:
        return min(mastery.get(c, 0.5) for c in it.concepts)

    def prereq_shortfall(it) -> int:
        return sum(1 for c in it.concepts for p in prereqs.get(c, []) if mastery.get(p, 0.5) < PREREQ_OK)

    cap = difficulty_cap(mastery)
    eligible = [it for it in items if it.difficulty <= cap]
    learning = [it for it in eligible if weakest(it) < GOAL]
    pool = learning or eligible or items
    # Prefer unseen items; repeat only when all have been seen
    unseen = [it for it in pool if it.id not in seen]
    pool = unseen or pool
    item = min(pool, key=lambda it: (weakest(it), prereq_shortfall(it), it.difficulty, it.id))
    return item


def explain(item, mastery: dict[str, float], prereqs: dict[str, list[str]]) -> str:
    weakest = min(item.concepts, key=lambda c: mastery.get(c, 0.5))
    missing = sorted({pre for c in item.concepts for pre in prereqs.get(c, []) if mastery.get(pre, 0.5) < PREREQ_OK})
    prereq_msg = (
        "prerequisites are met"
        if not missing
        else f"{len(missing)} prerequisite(s) not yet mastered: {', '.join(missing)} — de-prioritised, not hidden"
    )
    return (
        f"Targeting '{weakest}', your weakest skill in this question "
        f"(mastery {mastery.get(weakest, 0.5):.2f}). "
        f"You've earned difficulty tier {difficulty_cap(mastery)}. {prereq_msg}."
    )


def should_stop(mastery: dict[str, float], n: int, cap: int = 9) -> bool:
    return n >= cap or (mastery and min(mastery.values()) >= GOAL)
