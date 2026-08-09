from . import proplog


def _parse_01(text: str) -> int:
    t = text.strip().lower()
    if t in ('0', 'f', 'false', 'no'):
        return 0
    if t in ('1', 't', 'true', 'yes'):
        return 1
    raise ValueError("expected 0 or 1")


def _parse_yesno(text: str) -> bool:
    t = text.strip().lower()
    if t in ('y', 'yes', 'true', 't', '1', 'tautology', 'equivalent'):
        return True
    if t in ('n', 'no', 'false', 'f', '0', 'not'):
        return False
    raise ValueError("expected yes or no")


def grade(item, answer_text: str):
    """返回 (is_correct, expected_display)。"""
    p = item.payload
    if item.type == 'logic_eval':
        expected = proplog.evaluate(p['formula'], p['assignment'])
        return _parse_01(answer_text) == expected, str(expected)
    if item.type == 'tautology_check':
        expected = proplog.is_tautology(p['formula'])
        return _parse_yesno(answer_text) == expected, ("Yes" if expected else "No")
    if item.type == 'equivalence_check':
        expected = proplog.are_equivalent(p['formula1'], p['formula2'])
        return _parse_yesno(answer_text) == expected, ("Equivalent" if expected else "Not equivalent")
    if item.type == 'mcq':
        expected = p['answer_index']
        return int(answer_text) == expected, p['options'][expected]
    raise ValueError(f"unknown item type {item.type}")