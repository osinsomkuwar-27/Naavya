"""
referral_generate.py

Takes the output of imnci_lookup and produces two distinct messages:
  1. caregiver_message — plain-language text meant to be spoken/shown to
     the parent (this is what Shreeja's TTS layer will speak aloud)
  2. asha_alert — a shorter, clinical-shorthand message for the ASHA
     worker's SMS/WhatsApp alert, only generated when urgency is refer_now

Kept separate from imnci_lookup deliberately — classification is a
clinical decision, message generation is a presentation concern. Mixing
them would make the rule engine harder to test and reuse.
"""

from typing import Optional

_CAREGIVER_TEMPLATES = {
    "refer_now": (
        "This needs urgent attention. Please go to the nearest hospital "
        "or health facility right now, or contact your ASHA worker "
        "immediately. {action_summary}"
    ),
    "monitor_recheck": (
        "This should be watched carefully but does not need an urgent "
        "hospital visit right now. {action_summary} If anything gets "
        "worse before then, contact your ASHA worker or go to the "
        "nearest health facility immediately."
    ),
    "reassure": (
        "This is common and usually not a cause for concern. "
        "{action_summary}"
    ),
    "insufficient_data": (
        "I need a bit more information to be sure. Please contact your "
        "ASHA worker so they can check in person."
    ),
    "invalid_input": (
        "Something went wrong understanding the details. Please contact "
        "your ASHA worker directly to be safe."
    ),
}

_UNIVERSAL_RETURN_SIGNS_TEXT = (
    "Regardless of what was discussed, return immediately if the baby "
    "feeds or drinks poorly, becomes sicker, develops a fever or feels "
    "unusually cold, breathes fast or with difficulty, or if you see "
    "blood in the stool."
)


def referral_generate(lookup_result: dict, append_universal_signs: bool = True) -> dict:
    """
    Args:
        lookup_result: the dict returned by imnci_lookup()
        append_universal_signs: whether to append the standard "return
            immediately if..." safety-net line (recommended: True for
            monitor_recheck and reassure, since those are the cases where
            a caregiver might otherwise not know when to escalate later)

    Returns:
        {
            "caregiver_message": str,
            "asha_alert": str | None,   # only set when urgency is refer_now
        }
    """
    urgency = lookup_result.get("highest_urgency", "insufficient_data")
    action_summary = lookup_result.get("action_summary", "")

    template = _CAREGIVER_TEMPLATES.get(urgency, _CAREGIVER_TEMPLATES["insufficient_data"])
    caregiver_message = template.format(action_summary=action_summary)

    if lookup_result.get("confidence_note"):
        caregiver_message += " " + lookup_result["confidence_note"]

    if append_universal_signs and urgency in ("monitor_recheck", "reassure"):
        caregiver_message += " " + _UNIVERSAL_RETURN_SIGNS_TEXT

    asha_alert = None
    if urgency == "refer_now":
        rule_ids = ", ".join(lookup_result.get("matched_rule_ids", []))
        asha_alert = (
            f"URGENT REFERRAL FLAGGED — classification(s): {rule_ids}. "
            f"Caregiver has been advised to go to nearest facility now. "
            f"Please follow up as soon as possible."
        )

    return {
        "caregiver_message": caregiver_message,
        "asha_alert": asha_alert,
    }