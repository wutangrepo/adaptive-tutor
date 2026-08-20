from types import SimpleNamespace as mk
from app import approval


def test_same_value_rejected_across_machines():
    # "approved" exists in both graphs, but a hint draft must never jump to an
    # assessment-only state ("needs_human") just because the string is valid
    # somewhere. Each table is the single source of truth for its own machine.
    assert approval.hint_transition("draft", "approved") == "approved"
    try:
        approval.hint_transition("draft", "needs_human")
        raise AssertionError("cross-workflow move must be rejected")
    except ValueError:
        pass


def test_assessment_transitions():
    for cur in ("pending", "needs_human"):
        assert approval.assessment_transition(cur, "approved") == "approved"
        assert approval.assessment_transition(cur, "overridden") == "overridden"


def test_terminal_states_are_final():
    for machine in (approval.assessment_transition, approval.hint_transition):
        for terminal in ("approved", "rejected", "overridden"):
            try:
                machine(terminal, "pending")
                raise AssertionError(f"{terminal!r} must be terminal")
            except ValueError:
                pass


def test_unknown_state_rejected():
    try:
        approval.assessment_transition("shipped", "approved")
        raise AssertionError("unknown state must be rejected")
    except ValueError:
        pass