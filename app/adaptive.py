PREREQ_OK = 0.50        # Threshold for mastery of prerequisite concepts
GOAL = 0.75             # "mastered" threshold
K = 0.25                # Update speed: Move 25% toward the target from the current mastery level

def init_mastery(concepts, value=0.5):
    return {c: value for c in concepts}

def update(mastery, concepts, correct):
    out = 1.0 if correct else 0.0
    m = dict(mastery)
    for c in concepts:
        p = m.get(c, 0.5)
        m[c] = round(p + K * (out - p), 3)
    return m

def predicted(item, mastery):
    base = sum(mastery.get(c, 0.5) for c in item.concepts) / len(item.concepts)
    return max(0.05, min(0.95, round(base - 0.1 * (item.difficulty - 2), 3)))

def unlocked(item, mastery, prereqs):
    """True when every prerequisite of the item's concepts is mastered enough."""
    for c in item.concepts:
        for pre in prereqs.get(c, []):
            if mastery.get(pre, 0.5) < PREREQ_OK:
                return False
    return True

def difficulty_cap(mastery):
    """Highest item difficulty the learner has earned.

    Gate = the *best* mastery the learner has demonstrated.  Someone who keeps
    answering correctly raises a concept above the threshold and unlocks harder
    tiers; a learner who keeps getting things wrong only sees their mastery fall,
    so they stay on entry/intermediate problems (but are still shown a range of
    them, never funneled into one question).  This replaces the old brittle
    "prerequisite lock" that collapsed the whole pool after a single wrong answer.
    """
    strongest = max(mastery.values()) if mastery else 0.5
    if strongest >= 0.7:
        return 3
    if strongest >= 0.5:
        return 2
    return 1

def select(items, mastery, prereqs, seen):
    """Pick the next item for the learner.

    Policy (priority order):
      1. strongest deficiency -- serve the question covering the learner's
         weakest concept, so a miss is re-drilled instead of abandoned;
      2. prerequisite health -- prefer items whose prerequisites are met, but
         never hide an item just because one prerequisite is weak;
      3. simpler item first -- within a topic, start with the easier item;
      4. id -- deterministic tie-break (keeps output stable for tests).

    The pool never collapses from a single wrong answer: an item is only out of
    reach when its difficulty exceeds what the learner has earned (difficulty_cap).
    """
    def weakest(it):
        return min(mastery.get(c, .5) for c in it.concepts)

    def prereq_shortfall(it):
        return sum(1 for c in it.concepts
                   for p in prereqs.get(c, []) if mastery.get(p, .5) < PREREQ_OK)

    cap = difficulty_cap(mastery)
    eligible = [it for it in items if it.difficulty <= cap]
    learning = [it for it in eligible if weakest(it) < GOAL]
    pool = learning or eligible or items
    unseen = [it for it in pool if it.id not in seen]
    pool = unseen or pool          # 只有没新题可出时才重复
    item = min(pool, key=lambda it: (weakest(it), prereq_shortfall(it),
                                     it.difficulty, it.id))
    return item, predicted(item, mastery)

def explain(item, mastery, prereqs):
    weakest = min(item.concepts, key=lambda c: mastery.get(c, 0.5))
    missing = sorted({pre for c in item.concepts
                      for pre in prereqs.get(c, [])
                      if mastery.get(pre, 0.5) < PREREQ_OK})
    prereq = ("prerequisites are met"
              if not missing
              else f"{len(missing)} prerequisite(s) not yet mastered: "
                   f"{', '.join(missing)} — de-prioritised, not hidden")
    return (f"Targeting '{weakest}', your weakest skill in this question "
            f"(mastery {mastery.get(weakest, .5):.2f}). "
            f"You've earned difficulty tier {difficulty_cap(mastery)}. "
            f"{prereq}.")

def should_stop(mastery, n, cap=9):
    return n >= cap or (mastery and min(mastery.values()) >= GOAL)