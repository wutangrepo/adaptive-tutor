TARGET = (0.60, 0.75)   # Target prediction correctness band
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
    for c in item.concepts:
        for pre in prereqs.get(c, []):
            if mastery.get(pre, 0.5) < PREREQ_OK:
                return False
    return True

def band_distance(p):
    if p < TARGET[0]: return TARGET[0] - p
    if p > TARGET[1]: return p - TARGET[1]
    return 0.0

def select(items, mastery, prereqs, seen):
    elig = [it for it in items if unlocked(it, mastery, prereqs)]
    if not elig:
        return None, None
    learning = [it for it in elig
                if min(mastery.get(c, .5) for c in it.concepts) < GOAL]
    pool = learning or elig                      # All mastered → review mode
    item = min(pool, key=lambda it: (band_distance(predicted(it, mastery)),
                                     it.id in seen, it.id))
    return item, predicted(item, mastery)

def explain(item, p, mastery, prereqs):
    weakest = min(item.concepts, key=lambda c: mastery.get(c, 0.5))
    lo, hi = TARGET
    pos = ("inside" if lo <= p <= hi else "below" if p < lo else "above")
    return (f"Targeting '{weakest}' (mastery {mastery.get(weakest, .5):.2f}); "
            f"predicted success {p:.2f} is {pos} the target band {lo}–{hi}; "
            f"prerequisites met.")

def should_stop(mastery, n, cap=10):
    return n >= cap or (mastery and min(mastery.values()) >= GOAL)