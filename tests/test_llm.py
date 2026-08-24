import pytest

from app.llm import BadGrade, OllamaProvider, _extract_json

RUBRIC = [
    {"criterion": "identifies the connective", "points": 2},
    {"criterion": "correct final value", "points": 3},
]


def test_extract_json_from_fenced_output():
    raw = 'Sure! Here is the grade:\n```json\n{"confidence": 0.9}\n```\nHope that helps.'
    assert _extract_json(raw) == {"confidence": 0.9}


def test_extract_json_raises_without_object():
    with pytest.raises(BadGrade):
        _extract_json("I cannot grade that.")


def make_provider():
    # complete() is never called in these tests -- only validation logic runs.
    return OllamaProvider()


def test_valid_grade_passes_and_computes_totals():
    raw = '{"criteria": [{"awarded": 2}, {"awarded": 0}], "confidence": 0.8}'
    d = make_provider().validate_grade(raw, RUBRIC)
    assert d["total"] == 2
    assert d["max"] == 5
    assert [c["criterion"] for c in d["criteria"]] == \
        [s["criterion"] for s in RUBRIC]


def test_confidence_out_of_range_rejected():
    raw = '{"criteria": [{"awarded": 2}, {"awarded": 3}], "confidence": 1.5}'
    with pytest.raises(BadGrade):
        make_provider().validate_grade(raw, RUBRIC)


def test_wrong_criteria_count_rejected():
    raw = '{"criteria": [{"awarded": 2}], "confidence": 0.5}'
    with pytest.raises(BadGrade):
        make_provider().validate_grade(raw, RUBRIC)


def test_partial_points_rejected():
    raw = '{"criteria": [{"awarded": 1}, {"awarded": 3}], "confidence": 0.5}'
    with pytest.raises(BadGrade):
        make_provider().validate_grade(raw, RUBRIC)


def test_non_numeric_award_rejected():
    raw = '{"criteria": [{"awarded": "two"}, {"awarded": 3}], "confidence": 0.5}'
    with pytest.raises(BadGrade):
        make_provider().validate_grade(raw, RUBRIC)


def test_boolean_award_rejected():
    # True == 1, so without an explicit bool check it would pass the
    # (0, points) membership test when a criterion is worth 1 point.
    raw = '{"criteria": [{"awarded": true}, {"awarded": 3}], "confidence": 0.5}'
    with pytest.raises(BadGrade):
        make_provider().validate_grade(raw, RUBRIC)


def test_integral_float_award_accepted():
    raw = '{"criteria": [{"awarded": 2.0}, {"awarded": 3.0}], "confidence": 0.5}'
    d = make_provider().validate_grade(raw, RUBRIC)
    assert d["total"] == 5
    assert all(isinstance(c["awarded"], int) for c in d["criteria"])


def test_fractional_float_award_rejected():
    raw = '{"criteria": [{"awarded": 1.5}, {"awarded": 3}], "confidence": 0.5}'
    with pytest.raises(BadGrade):
        make_provider().validate_grade(raw, RUBRIC)


def test_string_award_and_confidence_rejected():
    raw = '{"criteria": [{"awarded": "2"}, {"awarded": 3}], "confidence": "0.8"}'
    with pytest.raises(BadGrade):
        make_provider().validate_grade(raw, RUBRIC)


def test_boolean_confidence_rejected():
    # isinstance(True, int) is True, so without the bool guard this would be
    # accepted as confidence == 1.
    raw = '{"criteria": [{"awarded": 2}, {"awarded": 3}], "confidence": true}'
    with pytest.raises(BadGrade):
        make_provider().validate_grade(raw, RUBRIC)
