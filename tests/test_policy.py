import random
from types import SimpleNamespace as mk
from app import adaptive

ITEMS = [mk(id="ex8-8-2", concepts=["statement","logical-connectives"], difficulty=1),
         mk(id="ex8-8-5", concepts=["statement","logical-connectives"], difficulty=1),
         mk(id="ex9-8-1", concepts=["tautology","zero-one-method"], difficulty=2),
         mk(id="ex9-9-6", concepts=["logical-equivalence"], difficulty=2),
         mk(id="ex11-4", concepts=["logical-function","function-evaluation"], difficulty=2),
         mk(id="ex11-6", concepts=["logical-function","function-evaluation"], difficulty=3)]
PREREQS = {"logical-connectives": ["statement"], "tautology": ["truth-table"],
           "zero-one-method": ["tautology"], "logical-equivalence": ["truth-table"],
           "logical-function": ["logical-connectives"],
           "function-evaluation": ["logical-function", "zero-one-method"]}
CONCEPTS = sorted({c for it in ITEMS for c in it.concepts} | set(PREREQS) | {"statement", "truth-table"})
PROFILES = {"novice": {"*": .25}, "expert": {"*": .9},
            "gappy": {"*": .85, "tautology": .2, "zero-one-method": .2}}

def run(profile, n=12):
    mastery, seq, seen = adaptive.init_mastery(CONCEPTS), [], set()
    for _ in range(n):
        item, p = adaptive.select(ITEMS, mastery, PREREQS, seen)
        if not item: break
        seq.append(item.id); seen.add(item.id)
        correct = all(profile.get(c, profile["*"]) > .5 for c in item.concepts)
        mastery = adaptive.update(mastery, item.concepts, correct)
    return seq, mastery

def test_paths_diverge():
    nov, exp, gap = run(PROFILES["novice"]), run(PROFILES["expert"]), run(PROFILES["gappy"])
    assert nov[0] != exp[0]                                  # question order differs
    assert "ex11-6" in exp[0] and "ex11-6" not in nov[0]     # expert with hard question, novice without
    assert sum(t in ("ex9-8-1",) for t in gap[0]) >= 1       # learners with gaps are directed to fill them
    assert exp[1]["function-evaluation"] > .7 > nov[1]["function-evaluation"]

def test_prereq_gate():
    m = adaptive.init_mastery(CONCEPTS); m["zero-one-method"] = .3
    it = [i for i in ITEMS if i.id == "ex11-4"][0]
    assert not adaptive.unlocked(it, m, PREREQS)               # prereq not met, gate locked

def test_update_rule():
    m = adaptive.update(adaptive.init_mastery(["tautology"]), ["tautology"], False)
    assert m["tautology"] == 0.375   # 0.5 + 0.25*(0-0.5) = 0.375