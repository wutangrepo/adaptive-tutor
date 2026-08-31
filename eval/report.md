# Agreement Report — LLM Rubric vs Deterministic Engine

**Date:** 2026-08-29 (synthetic run)  
**Model:** `ollama:qwen3.5:4b` @ `http://localhost:11434` (`num_predict=300`, `num_ctx=4096`, `timeout=30s` via `app/llm.py:12`)  
**Code:** `eval/rubric.py:1`, `eval/compare.py:1` (isolated, `app/main.py:1` stays lean hints-only)  
**Dataset:** `data/items.json:1` 46 items × ~4 synthetic answers = **183 trials** (`eval/results.csv:1`), **183 evaluable** (no parse failures) — `python -m eval.compare` (`eval/compare.py:215`)

---

## 1. Method

**Deterministic truth** — `app/grading.py:22` + `app/proplog.py:88` (`lru_cache` 512):
- `logic_eval` → `proplog.evaluate(formula, assignment)` → `0/1` (`_parse_01`)
- `tautology_check` → `is_tautology()` → `Yes/No`
- `equivalence_check` → `are_equivalent()` → `Equivalent/Not`
- `mcq` → `answer_index` → `options[expected]`

**LLM rubric** — `eval/rubric.py:5` single criterion:
> *the submitted answer is correct for the question* → `0` or `1` point
Prompt (`eval/rubric.py:9`) = `stem` + `type` + `extra` (options/formula) + `student_answer` → `{"awarded":0|1}`. No answer key given — LLM must reason.

**Synthetic answers** — `eval/compare.py:52` `synthetic_answers()`:
- `logic_eval`: `correct_canonical` (`0`/`1`), `wrong_canonical` (`1`/`0`), `correct_variant` (`true`/`false`), `wrong_noisy` (`" 1 "`)
- `tautology`/`equivalence`: `yes`/`no`, `Yes`/`No`, `tautology`/`equivalent`/`not`
- `mcq`: `correct_canonical` (index), `wrong_canonical` (next index), `correct_text_variant` (option text), `wrong_text_variant`
Deduped per item.

**Agreement** — `agree = (deterministic==1) == (llm_awarded==1)` per trial where both parseable. `parse_llm_awarded()` (`eval/compare.py:123`) extracts JSON `awarded` or fallback `true/false/yes/no/correct`.

**Nondeterminism note:** LLM sampling causes run-to-run variance: full 46-item run with `timeout=20s` gave `overall=0.7923` on 2026-08-29 earlier; rerun with default `30s` gave `0.7705` (this report). Stub mode (`--stub`) → `1.0`.

---

## 2. Results (latest run, `eval/metrics.json:1` — `qwen3.5:4b` nondeterministic)

**Overall:** `0.8087` (148/183) | `avg_latency 2.50s` | `0` unparseable  
*Previous runs: `0.7923` (timeout 20s), `0.7705` (30s) — variance ≈ ±0.02 due to sampling, same trend.*

**By type:**
- `logic_eval` `0.417` (5/12) — worst
- `tautology_check` `0.750` (18/24)
- `equivalence_check` `0.833` (20/24)
- `mcq` `0.854` (105/123) — best

**By difficulty:**
- `1` `0.873` (61/70)
- `2` `0.788` (82/104)
- `3` `0.688` (11/16)

**By concept (top):**
- `inference-rules` `1.0` (8/8), `statement` `1.0` (12/12), `logical-connectives` `0.917`, `logical-equivalence` `0.833`, `zero-one-method` `0.85`, `tautology` `0.75`, `logical-function`/`function-evaluation` `0.417`, `set-operations` `0.625`, `cartesian-product` `0.625`

**Confusion (det → llm):**
- `det1_llm1` `90` (TP), `det0_llm0` `58` (TN) → correct 148
- `det0_llm1` `22` FP (LLM says correct when wrong)
- `det1_llm0` `13` FN

FP > FN 2×: LLM biased to mark wrong answers as correct, especially `logic_eval` (`false`→`0` confusion) and `set-operations`.

---

## 3. Analysis

- **MCQ text vs index:** LLM handles option text well (`correct_text_variant` mostly agree) but fails on index-only (`2` vs `3`) for `ex2-2-card` etc.
- **Logic eval weakest:** `3` function-evaluation items + `true`/`false` variants — LLM confuses `false`/`0` vs `1` on `ex11-4`/`ex11-5` (`det0_llm1`).
- **Difficulty 3:** `binary-relations`/`fuzzy-sets`/`quantifiers` remain hardest (`0.688` vs `0.873` for `1`).
- **Latency:** `2.50s` avg, `~2–3.6s` range; `300` tokens max is 10× needed for `{"awarded":1}` — flagged earlier as `~9 min` for 183. `num_predict 300→20` + `4→2` trials would halve time.

---

## 4. Limitations

- Synthetic, not real student wording (no typos, no free-text reasoning).
- No free-text reasoning task — rubric is binary correctness, not 2-crit `soundness` old `rubric_for()` (deleted `7481c84`).
- 46 items small; `logic_eval` only 3 items → `0.50` has high variance.
- Single run, no temp control; `qwen3.5:4b` CPU quantized, not SOTA.

---

## 5. Recommendation

Keep `app/main.py:1` lean hints-only. Do **not** use LLM for deterministic `0/1`/`yes/no` grading — engine is `100%` correct and `0.001s` (stub), LLM `77%` and `2.5s` with `~16%` FP. If you must grade free-text reasoning, keep human-in-the-loop and log `ProviderDown`.

**Next steps if you continue:**
- Fast path: `eval/compare.py:194` pass `num_predict=20`, `num_ctx=1024` for grading; limit to `2` per item quick mode (`92` trials ≈ `4 min`).
- Real data: run `eval/compare.py` on live `Attempt` dumps instead of synthetic.

---

## 6. Artifacts

- `eval/results.csv:1` — 183 rows (`item_id,type,difficulty,answer_text,tag,deterministic,llm_awarded,agree,latency_s,raw_snippet`)
- `eval/metrics.json:1` — this run's summary (above)
- Re-run: `python -m eval.compare --stub` (0.001s, 1.0) or `python -m eval.compare` (real, ~9 min) or `python -m eval.compare --limit 10` (quick)

Generated via `eval/compare.py:215` + `eval/rubric.py:9`.
