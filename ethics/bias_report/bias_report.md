# Naavya — Bias & Fairness Report

**Component tested:** Classification logic (`mcp/tools/imnci_lookup.py` + `rule_engine.py`)
**Test suite:** `ethics/bias_report/test_cases.json`, executed via `run_bias_tests.py`
**Result:** 11/11 checks passed
**Owner:** Kshitij

## Why This Report Looks Different From a Typical ML Bias Audit

Naavya's classification layer is a **rule-based system grounded in a public clinical guideline** (IMNCI), not a trained machine learning model. There is no training data to audit for representation gaps, and no model weights that could have absorbed spurious correlations from a biased dataset. This changes what "bias testing" means here:

- There is no risk of the classifier learning a proxy for gender, caste, religion, or region, because **no such field exists anywhere in the input schema** — the system physically cannot see or use that information.
- The relevant fairness questions instead become: *is the logic deterministic and auditable, does it treat every clinically-identical case the same way, and is any intentional differential treatment (like the parent vs. ASHA confidence weighting) actually fair and directionally safe rather than arbitrary?*

## What Was Tested

### 1. Demographic Neutrality
Every field name in `data/imnci_rules/danger_signs.json` was scanned against a list of identity/demographic keywords (gender, caste, religion, name, ethnicity, region, language, income, etc.).

**Result:** 0 of 20 sign fields matched any prohibited category. The schema contains only clinical observations (feeding, breathing, temperature, jaundice, weight, etc.) — there is no mechanism by which classification could vary based on who the patient is, only on what symptoms are present.

### 2. Determinism
The same input, run 20 times, must produce byte-identical output every time — no hidden randomness that could make outcomes inconsistent for two patients with identical presentations.

**Result:** Passed. All 20 runs identical.

### 3. Source Fairness (ASHA-reported vs. Parent-reported)
This is the one place the system *intentionally* treats input differently depending on who reported it — parent-reported voice input gets a wider safety margin than an ASHA worker's structured checklist, since voice descriptions are inherently less precise. The fairness question isn't "are they treated the same" (by design, they aren't) but **"does the difference only ever move toward more caution, never less."**

Three cases tested:
- **Identical dangerous signs** (refer_now-level): both sources produced identical `refer_now` — urgent danger signs override any source-based weighting entirely, as they should.
- **Identical, fully-covered healthy signs**: both sources produced identical `reassure` — confirms the margin doesn't penalize parent-reported input once genuine coverage is confirmed (this was a real bug, found and fixed earlier — see commit history).
- **Identical, partially-covered signs**: ASHA-reported trusted the reassure classification; parent-reported was bumped to `monitor_recheck`. This is the intentional differential, and it moved in the safe direction only.

**Result:** All 3 passed. The fairness invariant — parent-reported urgency is never lower than ASHA-reported urgency for the same signs — held in every case tested.

### 4. Boundary Consistency
IMNCI's guideline has several hard age/count thresholds (7-day and 14-day age cutoffs, a 10-pustule severity cutoff). A classification system that's inconsistent right at a boundary would effectively be arbitrary for patients who happen to fall near that line.

Six boundary cases tested, including the exact day (age 7, age 14) and one day before it on both the breathing-rate severity split and the jaundice age-escalation trigger (the fix originally flagged by Shreeja's clinical review), plus the pustule-count severity split.

**Result:** All 6 passed. Every boundary resolves to the clinically correct side, with no off-by-one drift.

## Known Limitations (Disclosed, Not Resolved Here)

This report covers the classification logic only. It does **not** cover:

- **ASR accuracy bias** across accents, dialects, or regional speech patterns (owned by Soham's `asr/transcribe.py`) — a real potential bias surface, since transcription accuracy plausibly varies by region/dialect, but outside this component's scope to test.
- **Disambiguation question comprehension** across different literacy levels or spoken fluency (owned by Shreeja's `agents/disambiguation/`) — whether the follow-up questions are equally understandable to all callers is a genuine open question, not evaluated here.
- **Sample size**: this is a targeted, rule-boundary test suite (11 checks), not a statistical audit across thousands of randomized cases. Given the system is deterministic and rule-based rather than probabilistic, targeted boundary testing is the appropriate method — but it should be read as "no known inconsistency found," not "mathematically proven bias-free."

## How to Reproduce

```bash
cd ethics/bias_report
python3 run_bias_tests.py
```

Full machine-readable results are written to `results.json` after each run.