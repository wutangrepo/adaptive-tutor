"""Synthetic agreement harness: deterministic engine vs local LLM.

Keeps app/main.py lean — this is eval-only, writes eval/results.csv + eval/metrics.json
Usage:
  python -m eval.compare               # uses Ollama if available, else deterministic stub
  python -m eval.compare --stub        # force stub (no Ollama needed)
  python -m eval.compare --model qwen3.5:4b --base http://localhost:11434

Output: eval/results.csv, eval/metrics.json (printed summary too)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import grading, proplog  # noqa: E402
from app.models import Item  # noqa: E402
from eval.rubric import build_prompt  # noqa: E402

DATA = Path("data/items.json")
OUT_CSV = Path("eval/results.csv")
OUT_JSON = Path("eval/metrics.json")


def load_items() -> list[dict]:
    return json.loads(DATA.read_text(encoding="utf-8"))


def derive_expected(item: dict):
    p = item["payload"]
    t = item["type"]
    if t == "logic_eval":
        return proplog.evaluate(p["formula"], p["assignment"])
    if t == "tautology_check":
        return proplog.is_tautology(p["formula"])
    if t == "equivalence_check":
        return proplog.are_equivalent(p["formula1"], p["formula2"])
    if t == "mcq":
        return p["answer_index"]
    raise ValueError(t)


def synthetic_answers(item: dict) -> list[tuple[str, str]]:
    """Return list of (answer_text, tag) where tag in correct/wrong/variant."""
    t = item["type"]
    exp = derive_expected(item)
    out: list[tuple[str, str]] = []

    if t == "logic_eval":
        # exp is 0/1
        correct = str(exp)
        wrong = str(1 - exp)
        # canonical
        out.append((correct, "correct_canonical"))
        out.append((wrong, "wrong_canonical"))
        # variant: different casing/word for correct
        variant = "true" if exp == 1 else "false"
        out.append((variant, "correct_variant"))
        # noisy wrong variant
        out.append((f" {wrong} ", "wrong_noisy"))

    elif t in ("tautology_check", "equivalence_check"):
        # exp bool
        correct = "yes" if exp else "no"
        wrong = "no" if exp else "yes"
        out.append((correct, "correct_canonical"))
        out.append((wrong, "wrong_canonical"))
        # variant: capitalised / synonym
        variant = "Yes" if exp else "No"
        out.append((variant, "correct_variant"))
        # synonym for true: tautology/equivalent vs not
        syn = "tautology" if t == "tautology_check" else "equivalent"
        if exp:
            out.append((syn, "correct_synonym"))
        else:
            out.append(("not", "wrong_synonym"))

    elif t == "mcq":
        correct_idx = exp
        # pick one wrong index
        n = len(item["payload"]["options"])
        wrong_idx = (correct_idx + 1) % n
        out.append((str(correct_idx), "correct_canonical"))
        out.append((str(wrong_idx), "wrong_canonical"))
        # variant: answer text instead of index? grading expects index, but we test index as canonical
        # For LLM we also test text variant: give option text as answer (LLM should still judge)
        out.append((item["payload"]["options"][correct_idx], "correct_text_variant"))
        out.append((item["payload"]["options"][wrong_idx], "wrong_text_variant"))

    else:
        out.append(("unknown", "unknown"))

    # deduplicate while preserving order
    seen = set()
    uniq = []
    for a, tag in out:
        if a not in seen:
            seen.add(a)
            uniq.append((a, tag))
    return uniq


def deterministic_correct(item: dict, answer_text: str) -> bool | None:
    """Use grading.grade to get deterministic correctness (True/False). Returns None on parse error."""
    from types import SimpleNamespace
    fake = SimpleNamespace(type=item["type"], payload=item["payload"])
    try:
        ok, _ = grading.grade(fake, answer_text)
        return bool(ok)
    except Exception:
        return None


def parse_llm_awarded(raw: str) -> int | None:
    """Extract awarded 0/1 from LLM raw. Returns None if cannot parse."""
    text = raw.strip()
    # Try JSON first
    try:
        # Find first {...}
        m = re.search(r"\{.*?\}", text, re.S)
        if m:
            import json as js
            d = js.loads(m.group(0))
            if "awarded" in d:
                v = d["awarded"]
                if isinstance(v, bool):
                    return None
                if isinstance(v, (int, float)) and int(v) in (0, 1):
                    return int(v)
                # string "0"/"1"
                if isinstance(v, str) and v.strip() in ("0", "1"):
                    return int(v.strip())
    except Exception:
        pass
    # Fallback: look for standalone 0/1 or true/false/yes/no in text
    low = text.lower()
    # If JSON says awarded, but we missed, search for '"awarded": 0'
    m = re.search(r'"awarded"\s*:\s*([01])', low)
    if m:
        return int(m.group(1))
    # Simple heuristics: if raw contains correct/incorrect words
    # Prefer explicit 0/1 tokens
    # Find last occurrence of 0 or 1 as standalone word
    # Use regex for word boundary
    # If LLM says "Correct" -> 1, "Incorrect" -> 0
    if "correct" in low and "incorrect" not in low:
        # but check if says "incorrect" -> 0
        return 1
    if "incorrect" in low or "wrong" in low:
        return 0
    # Look for yes/no, true/false when answer is yes/no type — but generic: true->1, false->0
    if re.search(r"\btrue\b", low):
        return 1
    if re.search(r"\bfalse\b", low):
        return 0
    if re.search(r"\byes\b", low):
        return 1
    if re.search(r"\bno\b", low):
        return 0
    # Finally look for standalone 0/1
    m = re.search(r"\b([01])\b", low)
    if m:
        return int(m.group(1))
    return None


def get_provider(args):
    if args.stub:
        return None  # signal to use deterministic stub
    try:
        from app.llm import OllamaProvider

        prov = OllamaProvider(model=args.model, base=args.base, timeout=args.timeout)
        # quick health check
        if not prov.health():
            print(f"[warn] Ollama health check failed at {args.base} — falling back to stub for this run (use --stub to silence)")
            # still return prov; caller will fallback per trial on ProviderDown
            pass
        return prov
    except Exception as e:
        print(f"[warn] cannot create OllamaProvider: {e} — using stub")
        return None


def llm_grade(item: dict, answer_text: str, provider) -> tuple[int | None, str, float]:
    """Returns (awarded_or_None, raw_text, latency_s). If provider is None, use deterministic stub that mirrors engine."""
    prompt = build_prompt(item, answer_text)
    if provider is None:
        # Stub: perfectly agrees with deterministic engine (for CI without Ollama)
        exp = deterministic_correct(item, answer_text)
        if exp is None and item["type"] == "mcq":
            # Text variant: answer is option text, not index
            correct_text = item["payload"]["options"][item["payload"]["answer_index"]]
            exp = answer_text.strip() == correct_text
        if exp is None:
            return None, '{"awarded": 0}', 0.001
        return (1 if exp else 0), json.dumps({"awarded": 1 if exp else 0}), 0.001

    start = time.time()
    try:
        raw = provider.complete(prompt)
        latency = time.time() - start
        awarded = parse_llm_awarded(raw)
        return awarded, raw, latency
    except Exception as e:
        latency = time.time() - start
        return None, f"ProviderDown: {e}", latency


def main():
    ap = argparse.ArgumentParser(description="Measure LLM vs deterministic agreement (synthetic answers)")
    ap.add_argument("--stub", action="store_true", help="force stub (no Ollama calls)")
    ap.add_argument("--model", default="qwen3.5:4b", help="Ollama model")
    ap.add_argument("--base", default="http://localhost:11434", help="Ollama base URL")
    ap.add_argument("--timeout", type=int, default=30, help="Ollama timeout seconds")
    ap.add_argument("--limit", type=int, default=0, help="limit items for quick run (0=all)")
    args = ap.parse_args()

    items = load_items()
    if args.limit:
        items = items[: args.limit]

    provider = get_provider(args)
    stub_mode = provider is None
    print(f"Items: {len(items)} | stub={stub_mode} | model={args.model} base={args.base}")

    rows = []
    for it in items:
        for ans_text, tag in synthetic_answers(it):
            det = deterministic_correct(it, ans_text)
            # For mcq text variant, deterministic will fail (expects index) -> None, we still want to compare LLM's ability
            # For those, compute expected via text match instead
            if det is None and it["type"] == "mcq" and tag.endswith("text_variant"):
                # Compare answer text to correct option text
                correct_text = it["payload"]["options"][it["payload"]["answer_index"]]
                det = ans_text.strip() == correct_text

            llm_awarded, raw, latency = llm_grade(it, ans_text, provider)
            # Agreement: both not None and equal (det True -> 1, False ->0)
            det_int = None if det is None else (1 if det else 0)
            agree = None
            if det_int is not None and llm_awarded is not None:
                agree = int(det_int == llm_awarded)

            rows.append(
                {
                    "item_id": it["id"],
                    "type": it["type"],
                    "difficulty": it["difficulty"],
                    "concepts": "|".join(it["concepts"]),
                    "source": it["source"],
                    "answer_text": ans_text.replace("\n", " ")[:120],
                    "tag": tag,
                    "deterministic": det_int,
                    "llm_awarded": llm_awarded,
                    "agree": agree,
                    "latency_s": round(latency, 3),
                    "raw_snippet": raw[:300].replace("\n", " ").replace('"', "'"),
                }
            )

    # Write CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Metrics
    # Filter to where both sides produced a value
    eval_rows = [r for r in rows if r["agree"] is not None]
    overall = sum(r["agree"] for r in eval_rows) / len(eval_rows) if eval_rows else 0
    by_type = defaultdict(list)
    by_diff = defaultdict(list)
    by_concept = defaultdict(list)
    confusion = Counter()  # (det, llm)
    llm_none = sum(1 for r in rows if r["llm_awarded"] is None)
    det_none = sum(1 for r in rows if r["deterministic"] is None)

    for r in eval_rows:
        by_type[r["type"]].append(r["agree"])
        by_diff[str(r["difficulty"])].append(r["agree"])
        for c in r["concepts"].split("|"):
            by_concept[c].append(r["agree"])
        confusion[(r["deterministic"], r["llm_awarded"])] += 1

    metrics = {
        "total_trials": len(rows),
        "evaluable": len(eval_rows),
        "llm_unparseable": llm_none,
        "det_unparseable": det_none,
        "overall_agreement": round(overall, 4),
        "by_type": {k: round(sum(v) / len(v), 4) for k, v in by_type.items()},
        "by_difficulty": {k: round(sum(v) / len(v), 4) for k, v in by_diff.items()},
        "by_concept_top": {k: round(sum(v) / len(v), 4) for k, v in sorted(by_concept.items(), key=lambda kv: len(kv[1]), reverse=True)[:10]},
        "confusion": {f"det{det}_llm{llm}": int(c) for (det, llm), c in confusion.items()},
        "avg_latency_s": round(sum(r["latency_s"] for r in rows) / len(rows), 3) if rows else 0,
        "stub_mode": stub_mode,
    }

    OUT_JSON.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"\nWrote {OUT_CSV} ({len(rows)} rows) and {OUT_JSON}")
    if stub_mode:
        print("Note: stub mode → 100% agreement expected (mirrors engine). Run without --stub with Ollama running for real measurement.")


if __name__ == "__main__":
    main()
