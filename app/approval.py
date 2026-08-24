# State-transition rules for the review/approval workflows.
# Two independent machines live here and are deliberately kept apart:
# Future concern, e.g adding pending for hints:
# They share string values (e.g. "approved"), but mixing their legal
# transitions would allow nonsense moves such as a hint "draft" jumping to an
# assessment-only state like "needs_human".

ASSESSMENT_TRANSITIONS = {
    "pending": {"approved", "overridden"},
    "needs_human": {"approved", "overridden"},
}

HINT_TRANSITIONS = {
    "draft": {"approved", "rejected"},
}


def transition(graph, current, new):
    """Validate a move from `current` to `new` within `graph`.

    Returns `new` when the move is legal, otherwise raises ValueError.
    """
    if new not in graph.get(current, set()):
        raise ValueError(f"illegal transition {current!r} -> {new!r}")
    return new


def assessment_transition(current, new):
    """Validate a status change on an Assessment (Pydantic/SQLAlchemy agnostic)."""
    return transition(ASSESSMENT_TRANSITIONS, current, new)


def hint_transition(current, new):
    """Validate a status change on a HintDraft."""
    return transition(HINT_TRANSITIONS, current, new)