"""
agents/risk_combination/risk_agent.py
Owner: Kshitij

The LLM-facing Risk Combination Agent. Sits between Shreeja's
Disambiguation Agent output and her Escalation Agent input, calling
imnci_lookup (never reasoning clinically itself) and adapting formats
on both sides.

This file exists specifically to fix three contract mismatches found
when integrating Soham/Shreeja's code against the imnci_rules schema:

  1. source string mismatch: their pipeline emits "parent_reported_voice",
     but imnci_lookup's confidence-weighting checks for exactly
     "parent_reported". Fixed via normalize_source().

  2. jaundice_onset never populated: Shreeja's jaundice_age disambiguation
     resolves to {"age_days", "jaundice_onset_day", "age_14_days_or_more_
     with_jaundice"} -- none of which is the "jaundice_onset" enum field
     the rule engine actually checks. Fixed via derive_jaundice_onset().

  3. Output shape mismatch: imnci_lookup returns {"classifications": [...],
     "highest_urgency": ...}, but Shreeja's EscalationAgent.handle()
     expects a single {"classification", "urgency", "action_summary"}.
     Fixed via adapt_for_escalation().

IMPORTANT: fixes 1 and 2 are patches applied here as a defensive
translation layer so the pipeline works today. The root cause in
Soham's/Shreeja's files should still be corrected at the source --
see the suggested diffs in the integration review. This file should
NOT be treated as a permanent workaround; once their files are updated,
normalize_source() and derive_jaundice_onset() become redundant
safety nets rather than load-bearing fixes.
"""

from typing import Optional
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp"))
from tools.imnci_lookup import imnci_lookup 

def normalize_source(raw_source: str) -> str:
    """
    Maps any variant of a parent/ASHA source string to exactly what
    imnci_lookup's confidence-weighting checks for. Uses startswith
    rather than an exact-match dict so future variants (e.g.
    "parent_reported_text", "parent_reported_whatsapp") don't silently
    fall through the same way "parent_reported_voice" did.
    """
    if not raw_source:
        return "parent_reported"  
    if raw_source.startswith("parent_reported"):
        return "parent_reported"
    if raw_source.startswith("asha_reported"):
        return "asha_reported"
    return "parent_reported"


def derive_jaundice_onset(signs: dict) -> dict:
    """
    If signs contains jaundice_onset_day (from Shreeja's _parse_age_answer)
    but not the jaundice_onset enum imnci_lookup actually needs, derive it.

    IMNCI's severe-jaundice trigger cares whether onset was within the
    first 24 hours of life. Shreeja's disambiguation gives onset_day as
    "the infant's age in days when jaundice first appeared" -- appearing
    on day 0 or 1 of life is the closest available proxy for "before 24
    hours" given a day-granularity answer (an hour-level answer isn't
    realistic to expect from a worried parent on a voice call).

    Returns a NEW dict (does not mutate the input) with jaundice_onset
    added if it could be derived, plus everything else unchanged.
    """
    result = dict(signs)

    if "jaundice_onset" in result:
        return result  
    onset_day = result.get("jaundice_onset_day")
    age_flag = result.get("age_14_days_or_more_with_jaundice")

    if onset_day is None and age_flag is None:
        return result  

    if onset_day is not None:
        result["jaundice_onset"] = (
            "onset_before_24_hours" if onset_day <= 1 else "onset_after_24_hours"
        )
    elif age_flag is not None:
        result["jaundice_onset"] = "onset_after_24_hours"

    return result

_URGENCY_TO_ESCALATION_KEY = {
    "refer_now": "refer_now",
    "monitor_recheck": "monitor_recheck",
    "reassure": "reassure",
}


def adapt_for_escalation(lookup_result: dict) -> dict:
    """
    Converts imnci_lookup's {"classifications": [...], "highest_urgency":
    ...} into the single-rule shape EscalationAgent.build_reply() expects:
    {"classification", "urgency", "action_summary", "follow_up_days"}.

    Picks the classification whose urgency matches highest_urgency (the
    one that actually drove the decision), and folds any confidence_note
    into the action_summary so it isn't silently dropped.
    """
    highest_urgency = lookup_result.get("highest_urgency")
    classifications = lookup_result.get("classifications", [])

    if highest_urgency in ("invalid_input", "insufficient_data"):
        return {
            "classification": highest_urgency,
            "urgency": "refer_now", 
            "action_summary": lookup_result.get("action_summary", ""),
            "follow_up_days": None,
        }

    driving_rule = next(
        (c for c in classifications if c["urgency"] == highest_urgency),
        classifications[0] if classifications else None,
    )

    if driving_rule is None:
        return {
            "classification": "unknown",
            "urgency": "refer_now",
            "action_summary": "Unable to determine classification. Advise contacting ASHA worker.",
            "follow_up_days": None,
        }

    action_summary = driving_rule["action_summary"]
    if lookup_result.get("confidence_note"):
        action_summary += " " + lookup_result["confidence_note"]

    return {
        "classification": driving_rule["classification"],
        "urgency": highest_urgency,
        "action_summary": action_summary,
        "follow_up_days": 2,
    }

def run_risk_combination(disambiguation_output: dict) -> dict:
    """
    Full entrypoint. Takes Shreeja's build_output()/process_intake() shape:
        {"source", "confidence", "signs", "unresolved_signs", "safe_fallback_message", ...}

    Returns a dict with BOTH:
      - "raw_lookup": the full imnci_lookup result, for logging/audit
      - "escalation_input": the adapted shape ready to pass directly into
        EscalationAgent.handle() as risk_output

    If safe_fallback_message is set (Shreeja's guardrail already fired),
    this function short-circuits and does NOT call imnci_lookup at all --
    her guardrail takes priority, matching the same "don't guess on
    ambiguous input" principle imnci_lookup itself follows.
    """
    if disambiguation_output.get("safe_fallback_message"):
        return {
            "raw_lookup": None,
            "escalation_input": {
                "classification": "unresolved_input",
                "urgency": "refer_now",
                "action_summary": disambiguation_output["safe_fallback_message"],
                "follow_up_days": None,
            },
        }

    raw_source = disambiguation_output.get("source", "")
    signs = disambiguation_output.get("signs", {})

    normalized_source = normalize_source(raw_source)
    signs = derive_jaundice_onset(signs)

    lookup_result = imnci_lookup(signs, source=normalized_source)
    escalation_input = adapt_for_escalation(lookup_result)

    return {
        "raw_lookup": lookup_result,
        "escalation_input": escalation_input,
    }


if __name__ == "__main__":
    import json

    print("=" * 70)
    print("TEST 1 -- Shreeja's 16-day jaundice case (Bug 2 regression test)")
    print("=" * 70)
    disambig_output_1 = {
        "source": "parent_reported_voice",
        "confidence": "probed",
        "signs": {
            "jaundice_extent": "face_or_body_only",
            "age_days": 16,
            "jaundice_onset_day": 10,
            "age_14_days_or_more_with_jaundice": True,
        },
        "unresolved_signs": [],
        "safe_fallback_message": None,
    }
    result_1 = run_risk_combination(disambig_output_1)
    print(json.dumps(result_1, indent=2))
    assert result_1["escalation_input"]["urgency"] == "refer_now", (
        "Expected refer_now once jaundice_onset is correctly derived and "
        "age >= 14 days -- this was broken before the Bug 2 fix"
    )

    print("\n" + "=" * 70)
    print("TEST 2 -- source normalization (Bug 1 regression test)")
    print("=" * 70)
    disambig_output_2 = {
        "source": "parent_reported_voice",
        "signs": {
            "jaundice_onset": "no_jaundice",
            "feeding": "feeding_normally",
            "breathing_rate": "normal",
        },
        "safe_fallback_message": None,
    }
    result_2 = run_risk_combination(disambig_output_2)
    print(json.dumps(result_2, indent=2))
    assert result_2["raw_lookup"]["confidence_note"] is not None, (
        "Expected the parent safety margin to fire on this ambiguous-ish case"
    )
    assert result_2["escalation_input"]["urgency"] == "monitor_recheck", (
        "Bug 4: adapter must use the safety-margin-bumped highest_urgency, "
        "not the original driving rule's urgency -- got: "
        f"{result_2['escalation_input']['urgency']}"
    )
    print("\n" + "=" * 70)
    print("TEST 3 -- escalation_input shape check (Bug 3 regression test)")
    print("=" * 70)
    esc_input = result_1["escalation_input"]
    required_keys = {"classification", "urgency", "action_summary"}
    assert required_keys.issubset(esc_input.keys()), (
        f"Missing keys for EscalationAgent.build_reply(): "
        f"{required_keys - esc_input.keys()}"
    )
    print("Shape OK:", esc_input)

    print("\n" + "=" * 70)
    print("ALL RISK AGENT TESTS PASSED")
    print("=" * 70)