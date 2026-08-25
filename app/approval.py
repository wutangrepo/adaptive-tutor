# State-transition rules for the hint review workflow.

HINT_TRANSITIONS = {
    "draft": {"approved", "rejected"},
}


def hint_transition(current, new):
    """Validate a status change on a HintDraft."""
    if new not in HINT_TRANSITIONS.get(current, set()):
        raise ValueError(f"illegal transition {current!r} -> {new!r}")
    return new