from app import proplog


def test_ex11_4():      # Exercise 11, Ex 4
    assert proplog.evaluate("(x1 ⊕ x2) ⊕ (x1 ∨ x2)", {"x1": 1, "x2": 0}) == 0


def test_ex11_5():      # Exercise 11, Ex 5
    assert proplog.evaluate("(x1 ⊕ x2) ∧ (¬x1 ⊕ x2)", {"x1": 1, "x2": 1}) == 0


def test_ex11_6():      # Exercise 11, Ex 6
    assert proplog.evaluate("(x1 ⊕ x2) ∧ (x1 ⊕ x3) ∧ (¬x2 ∨ ¬x3)",
                            {"x1": 1, "x2": 1, "x3": 0}) == 0


def test_ex9_8_tautologies():   # Exercise 9, Ex 8 All 5 subquestions
    for f in ["(A ∧ B) → A", "A → (A ∨ B)", "¬A → (A → B)",
              "(A ∧ B) → (A → B)", "¬(A → B) → ¬B"]:
        assert proplog.is_tautology(f), f


def test_ex9_9_demorgan():      # Exercise 9, Ex 9(6)
    assert proplog.are_equivalent("¬(B ∧ C)", "¬B ∨ ¬C")


def test_ex9_9_implication():   # Exercise 9, Ex 9(7)
    assert proplog.are_equivalent("A → B", "¬A ∨ B")


def test_course_example_9_11_not_tautology():
    # Lecture 9, Example 9.11 explicitly states that this is not a tautology.
    assert not proplog.is_tautology("(A → B) → (¬A → ¬B)")