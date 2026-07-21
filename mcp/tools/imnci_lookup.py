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
        confidence_note = _apply_parent_safety_margin(matches, highest_urgency, signs)
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


def _apply_parent_safety_margin(matches: list, highest_urgency: str, signs: dict) -> Optional[str]:
    """Parent-reported input is inherently less structured than an ASHA's
    trained checklist. But bumping urgency just because a matched rule's
    chart_section is CAPABLE of being dangerous (the original approach)
    over-triggers badly: bacterial_infection_none, jaundice_none, etc.
    all live in risky-capable sections, so a genuinely healthy baby with
    every relevant sign explicitly reported as normal would still get
    bumped from reassure to monitor_recheck every time -- defeating the
    point of ever reassuring a parent.

    Fixed approach: only bump if the caregiver's signs dict has ZERO
    coverage of the relevant category (i.e. we have no information at
    all about it, not just an inferred-normal absence). If at least one
    relevant sign was explicitly reported, trust the classification --
    that's exactly what disambiguation questions are for, and a
    confirmed-normal answer should be allowed to mean reassure.
    """
    RISKY_CATEGORY_COVERAGE = {
        "Check for Possible Bacterial Infection": {
            "feeding", "convulsions", "breathing_rate", "temperature",
            "movement", "nasal_flaring", "grunting", "bulging_fontanelle",
            "skin_pustules", "umbilicus",
        },
        "Check for Jaundice": {"jaundice_onset", "jaundice_extent", "age_days"},
        "Diarrhoea - Classify for Dehydration": {
            "diarrhoea_present", "hydration_signs", "movement",
        },
    }

    if highest_urgency != "reassure":
        return None

    touched_sections = {m["chart_section"] for m in matches if m["chart_section"]}
    uncovered_sections = []

    for section in touched_sections:
        coverage_keys = RISKY_CATEGORY_COVERAGE.get(section)
        if not coverage_keys:
            continue
        if not (coverage_keys & signs.keys()):
            uncovered_sections.append(section)

    if uncovered_sections:
        return (
            "Input was parent-reported and did not cover: "
            f"{', '.join(uncovered_sections)}. Applying a wider safety "
            "margin: recommend monitor/recheck rather than full "
            "reassurance until these are confirmed via disambiguation."
        )
    return None