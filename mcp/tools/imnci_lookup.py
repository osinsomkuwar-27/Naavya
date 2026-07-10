"""
imnci_lookup.py

The public tool function exposed via MCP. Given structured infant signs
and the input source (asha_reported vs parent_reported), returns every
matching IMNCI classification, the highest-priority urgency level, and
a combined action summary — with full traceability to rule_id/chart_section.
"""

from typing import Optional
from .rule_engine import RuleEngine
from .validator import validate_signs

_engine = RuleEngine()

URGENCY_PRIORITY = {"refer_now": 3, "monitor_recheck": 2, "reassure": 1}


def imnci_lookup(signs: dict, source: str = "asha_reported") -> dict:
    """
    Args:
        signs: structured sign values matching danger_signs.json keys, e.g.
            {
                "feeding": "not_able_to_feed_at_all",
                "breathing_rate": "fast_breathing",
                "age_days": 9,
                ...
            }
        source: "asha_reported" or "parent_reported" — determines confidence
            weighting applied on top of the raw rule matches.

    Returns:
        {
            "classifications": [...],
            "highest_urgency": "refer_now" | "monitor_recheck" | "reassure" | "invalid_input",
            "action_summary": str,
            "matched_rule_ids": [...],
            "confidence_note": str | None,
            "validation": { "valid": bool, "errors": [...], "warnings": [...] }
        }
    """
    validation = validate_signs(signs)

    if not validation["valid"]:
        return {
            "classifications": [],
            "highest_urgency": "invalid_input",
            "action_summary": (
                "Input contains invalid sign values and cannot be safely "
                "classified. Fix the flagged errors and resubmit, or ask "
                "the caregiver a clarifying question to correct the signs."
            ),
            "matched_rule_ids": [],
            "confidence_note": None,
            "validation": validation,
        }

    matches = _engine.evaluate(signs)

    if not matches:
        return {
            "classifications": [],
            "highest_urgency": "insufficient_data",
            "action_summary": (
                "Not enough structured signs to classify. Ask the caregiver "
                "for the missing details before giving guidance, or advise "
                "contacting the ASHA worker directly if information stays unclear."
            ),
            "matched_rule_ids": [],
            "confidence_note": None,
            "validation": validation,
        }

    highest = max(matches, key=lambda m: URGENCY_PRIORITY.get(m["urgency"], 0))
    highest_urgency = highest["urgency"]

    confidence_note = None
    if source == "parent_reported":
        confidence_note = _apply_parent_safety_margin(matches, highest_urgency)
        if confidence_note:
            highest_urgency = _bump_urgency(highest_urgency)

    action_summary = " ".join(dict.fromkeys(m["action_summary"] for m in matches))

    return {
        "classifications": matches,
        "highest_urgency": highest_urgency,
        "action_summary": action_summary,
        "matched_rule_ids": [m["rule_id"] for m in matches],
        "confidence_note": confidence_note,
        "validation": validation,
    }


def _bump_urgency(urgency: str) -> str:
    """Moves reassure -> monitor_recheck when a wider safety margin applies.
    Never suppresses an existing refer_now, and never invents a refer_now
    out of a reassure — only narrows the gap by one level."""
    if urgency == "reassure":
        return "monitor_recheck"
    return urgency


def _apply_parent_safety_margin(matches: list, highest_urgency: str) -> Optional[str]:
    """Parent-reported input is inherently less structured than an ASHA's
    trained checklist. If the classification landed on 'reassure' but ANY
    matched rule sits in a chart section that also contains refer_now-level
    classifications (i.e. the sign category is capable of being dangerous),
    flag it for a wider margin rather than trusting a clean 'reassure'
    off potentially under-described parent input."""
    risky_sections = {
        "Check for Possible Bacterial Infection",
        "Check for Jaundice",
        "Diarrhoea - Classify for Dehydration",
    }
    if highest_urgency == "reassure":
        touched_sections = {m["chart_section"] for m in matches if m["chart_section"]}
        if touched_sections & risky_sections:
            return (
                "Input was parent-reported and touches a category that can "
                "be serious. Applying a wider safety margin: recommend "
                "monitor/recheck rather than full reassurance, and confirm "
                "with disambiguation questions if not already asked."
            )
    return None