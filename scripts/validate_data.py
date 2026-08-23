"""Validate data/items.json against data/domain_map.json, then seed."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import proplog  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"

items = json.loads((DATA / "items.json").read_text(encoding="utf-8"))
dm = json.loads((DATA / "domain_map.json").read_text(encoding="utf-8"))
concepts = {c["id"] for c in dm["concepts"]}
prereqs = {c["id"]: c.get("prereqs", []) for c in dm["concepts"]}

errors = []
ids = [it["id"] for it in items]
dupes = {i for i in ids if ids.count(i) > 1}
if dupes:
    errors.append(f"duplicate item ids: {dupes}")

for it in items:
    if it["difficulty"] not in (1, 2, 3):
        errors.append(f"{it['id']}: difficulty must be 1..3")
    for c in it["concepts"]:
        if c not in concepts:
            errors.append(f"{it['id']}: unknown concept {c!r}")
    p = it["payload"]
    if it["type"] == "mcq":
        n = len(p["options"])
        if not (0 <= p["answer_index"] < n):
            errors.append(f"{it['id']}: answer_index out of range")
        if len(set(p["options"])) != n:
            errors.append(f"{it['id']}: duplicate options")

for cid, pres in prereqs.items():
    for pre in pres:
        if pre not in concepts:
            errors.append(f"concept {cid!r}: unknown prerequisite {pre!r}")

# every concept should be covered by at least one item
covered = {c for it in items for c in it["concepts"]}
uncovered = concepts - covered
if uncovered:
    errors.append(f"concepts with no items: {sorted(uncovered)}")


def derive(rec):
    p = rec["payload"]
    if rec["type"] == "logic_eval":
        return proplog.evaluate(p["formula"], p["assignment"])
    if rec["type"] == "tautology_check":
        return proplog.is_tautology(p["formula"])
    if rec["type"] == "equivalence_check":
        return proplog.are_equivalent(p["formula1"], p["formula2"])
    if rec["type"] == "mcq":
        return p["options"][p["answer_index"]]
    return _NO_DERIVATION  # LLM/rubric-graded types: nothing to derive here


_NO_DERIVATION = object()  # sentinel for types without deterministic answers

unknown_types = set()
for it in items:
    try:
        got = derive(it)
        if got is _NO_DERIVATION:
            unknown_types.add(it["type"])
    except Exception as e:  # noqa: BLE001
        errors.append(f"{it['id']}: cannot derive expected value ({e})")

if unknown_types:
    print(f"note: {sum(1 for i in items if i['type'] in unknown_types)} item(s) "
          f"of non-deterministic type(s) {sorted(unknown_types)} -- they are "
          f"graded by the AI rubric flow, not by derive(); verify manually")

print(f"{len(items)} items, {len(concepts)} concepts, "
      f"{len(covered)} concepts covered by items")
print(f"item type mix: "
      f"{ {t: sum(1 for i in items if i['type'] == t) for t in {i['type'] for i in items}} }")
if errors:
    print("PROBLEMS:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("all checks passed")
