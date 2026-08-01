from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


class Urgency:
    REFER_NOW = "refer_now"
    MONITOR_RECHECK = "monitor_recheck"
    REASSURE = "reassure"


# ---------------------------------------------------------------------------
# Reply templates. Keep them in plain, non-alarming, non-technical language
# — this is what actually gets spoken back to a parent via TTS.
# Placeholders like {classification} get filled from the Risk Combination
# Agent's output (see build_reply()).
# ---------------------------------------------------------------------------

TEMPLATES = {
    Urgency.REFER_NOW: (
        "This could be serious ({classification}). Please take the baby "
        "to your ASHA worker or the nearest health facility right now — "
        "do not wait for the next scheduled visit."
    ),
    Urgency.MONITOR_RECHECK: (
        "This looks like something to keep an eye on ({classification}). "
        "{action_summary} If it gets worse, or the baby stops feeding, "
        "seems too hot or cold, or has trouble breathing, go to the "
        "ASHA worker or nearest facility immediately."
    ),
    Urgency.REASSURE: (
        "This looks common in newborns and usually isn't a cause for "
        "worry ({classification}). {action_summary} Still, if you ever "
        "see the baby refusing to feed, breathing fast or with effort, "
        "or feeling unusually hot or cold, contact your ASHA worker "
        "right away."
    ),
}

SAFE_FALLBACK_TEMPLATE = (
    "I couldn't fully understand all the details, and I don't want to "
    "guess wrong. To be safe, please get the baby checked by your ASHA "
    "worker or nearest health facility today."
)

ASHA_ALERT_TEMPLATE = (
    "[ASHA ALERT] Household: {household_id}. Signs flagged: {signs}. "
    "Classification: {classification}. Source: {source}. "
    "Please follow up urgently."
)


@dataclass
class EscalationOutput:
    urgency: str
    reply_text: str
    language: str = "en"
    asha_alert_sent: bool = False
    asha_alert_text: Optional[str] = None
    log_entry: dict = field(default_factory=dict)
    follow_up_date: Optional[str] = None


class EscalationAgent:
    def __init__(self, language: str = "en"):
        self.language = language

    def build_reply(self, risk_output: dict, signs: dict = None) -> str:
        """
        risk_output is expected to come from the Risk Combination Agent,
        shaped roughly like one matched rule from combination_rules.json:
        {
          "classification": "severe_jaundice",
          "urgency": "refer_now",
          "action_summary": "...",
        }

        signs: the resolved clear_signs dict (feeding, breathing_rate,
        temperature, etc). Optional for backward compatibility, but
        should always be passed -- without it, two clinically different
        cases that happen to match the same rule category (e.g.
        "not feeding at all" vs "reduced feeding") produce IDENTICAL
        reply text, which is a real trust/safety weakness in a sensitive
        domain: the caregiver never learns WHY they're being told to
        act, only the broad category. Confirmed live: two different
        real test cases both returned byte-identical recommendation
        text before this fix.
        """
        urgency = risk_output["urgency"]
        template = TEMPLATES.get(urgency, SAFE_FALLBACK_TEMPLATE)
        reply = template.format(
            classification=risk_output.get("classification", "this condition").replace("_", " "),
            action_summary=risk_output.get("action_summary", ""),
        )

        if signs:
            signs_summary = self._describe_signs(signs)
            if signs_summary:
                reply += f" Based on what you told us: {signs_summary}."

        return reply

    _SIGN_DESCRIPTIONS = {
        "not_able_to_feed_at_all": "the baby is not able to feed at all",
        "not_feeding_well": "the baby is feeding less than usual",
        "fast_breathing": "fast breathing",
        "severe_chest_indrawing": "the chest pulling in while breathing",
        "fever_37_5C_or_above_or_hot_to_touch": "a fever or feeling unusually hot",
        "low_temp_below_35_5C_or_cold_to_touch": "feeling unusually cold",
        "convulsing_now": "the baby is having convulsions",
        "no_movement_at_all": "the baby is not moving",
        "moves_only_when_stimulated": "the baby only moves when touched",
        "palms_or_soles_yellow": "yellowing spread to the palms or soles",
        "ten_or_more_or_big_boil": "multiple skin pustules or a large boil",
    }

    def _describe_signs(self, signs: dict) -> str:
        """Turns the raw resolved signs dict into a short, plain-language
        list of what was actually reported -- the caregiver should see
        their own words reflected back, not just a broad category."""
        descriptions = []
        for value in signs.values():
            desc = self._SIGN_DESCRIPTIONS.get(value)
            if desc:
                descriptions.append(desc)
        return ", ".join(descriptions)

    def maybe_alert_asha(self, risk_output: dict, signs: dict, household_id: str, source: str):
        """Only refer_now cases page the ASHA worker — keeps her load
        realistic per the responsibility table."""
        if risk_output["urgency"] != Urgency.REFER_NOW:
            return False, None

        alert_text = ASHA_ALERT_TEMPLATE.format(
            household_id=household_id,
            signs=signs,
            classification=risk_output.get("classification", "unclassified"),
            source=source,
        )
        # PoC stage: simulate the alert rather than wire real SMS/WhatsApp.
        print(alert_text)
        return True, alert_text

    def compute_follow_up_date(self, risk_output: dict) -> Optional[str]:
        """monitor_recheck cases get a scheduled recheck; refer_now and
        reassure don't need one (refer_now is immediate, reassure has no
        forced check-in unless the rule table says otherwise)."""
        if risk_output["urgency"] != Urgency.MONITOR_RECHECK:
            return None
        days_out = risk_output.get("follow_up_days", 2)  # IMNCI default is 2 days
        return (datetime.now() + timedelta(days=days_out)).date().isoformat()

    def build_log_entry(
        self, risk_output: dict, signs: dict, source: str, household_id: str,
        asha_alert_sent: bool, follow_up_date: Optional[str]
    ) -> dict:
        """Shape matches what Osin's db/schema.sql logging table expects —
        anonymized (household_id, not a name/phone number)."""
        return {
            "timestamp": datetime.now().isoformat(),
            "household_id": household_id,
            "source": source,
            "signs": signs,
            "classification": risk_output.get("classification"),
            "urgency": risk_output["urgency"],
            "asha_alert_sent": asha_alert_sent,
            "follow_up_date": follow_up_date,
        }

    def handle(
        self,
        risk_output: dict,
        disambiguation_output: dict,
        household_id: str = "unknown_household",
    ) -> EscalationOutput:
        """
        Main entrypoint. Combines:
          - risk_output: from Kshitij's Risk Combination Agent
          - disambiguation_output: from my disambiguation_agent.py
            (build_output() shape — has signs, safe_fallback_message, etc.)
        """
        signs = disambiguation_output.get("signs", {})
        source = disambiguation_output.get("source", "unknown")

        # Guardrail: unresolved input overrides everything else — never
        # let a confident-sounding classification through on ambiguous
        # signs. This mirrors the Disambiguation Agent's own guardrail.
        if disambiguation_output.get("safe_fallback_message"):
            reply_text = SAFE_FALLBACK_TEMPLATE
            asha_alert_sent, asha_alert_text = self.maybe_alert_asha(
                {"urgency": Urgency.REFER_NOW, "classification": "unresolved_input"},
                signs, household_id, source,
            )
            log_entry = self.build_log_entry(
                {"urgency": Urgency.REFER_NOW, "classification": "unresolved_input"},
                signs, source, household_id, asha_alert_sent, None,
            )
            return EscalationOutput(
                urgency=Urgency.REFER_NOW,
                reply_text=reply_text,
                language=disambiguation_output.get("language", "en"),
                asha_alert_sent=asha_alert_sent,
                asha_alert_text=asha_alert_text,
                log_entry=log_entry,
                follow_up_date=None,
            )

        reply_text = self.build_reply(risk_output, signs=signs)
        asha_alert_sent, asha_alert_text = self.maybe_alert_asha(
            risk_output, signs, household_id, source
        )
        follow_up_date = self.compute_follow_up_date(risk_output)
        log_entry = self.build_log_entry(
            risk_output, signs, source, household_id, asha_alert_sent, follow_up_date
        )

        return EscalationOutput(
            urgency=risk_output["urgency"],
            reply_text=reply_text,
            language=disambiguation_output.get("language", "en"),
            asha_alert_sent=asha_alert_sent,
            asha_alert_text=asha_alert_text,
            log_entry=log_entry,
            follow_up_date=follow_up_date,
        )

if __name__ == "__main__":
    import json

    agent = EscalationAgent()

    print("=" * 70)
    print("CASE 1 — refer_now (fast breathing + not feeding)")
    print("=" * 70)
    risk_output_1 = {
        "classification": "possible_serious_bacterial_infection_or_very_severe_disease",
        "urgency": Urgency.REFER_NOW,
        "action_summary": "Refer urgently to hospital.",
    }
    disambig_output_1 = {
        "source": "parent_reported_voice",
        "signs": {"feeding": "not_able_to_feed_at_all", "breathing_rate": "fast_breathing"},
        "safe_fallback_message": None,
    }
    result_1 = agent.handle(risk_output_1, disambig_output_1, household_id="HH-1042")
    print(json.dumps(result_1.__dict__, indent=2))

    print("\n" + "=" * 70)
    print("CASE 2 — reassure (mild face-only jaundice, day 10, onset day 3)")
    print("=" * 70)
    risk_output_2 = {
        "classification": "jaundice",
        "urgency": Urgency.MONITOR_RECHECK,
        "action_summary": "Advise home care. Tell caregiver to return immediately if palms/soles turn yellow.",
        "follow_up_days": 2,
    }
    disambig_output_2 = {
        "source": "parent_reported_voice",
        "signs": {"jaundice_extent": "face_or_body_only", "age_days": 10, "jaundice_onset_day": 3},
        "safe_fallback_message": None,
    }
    result_2 = agent.handle(risk_output_2, disambig_output_2, household_id="HH-2077")
    print(json.dumps(result_2.__dict__, indent=2))

    print("\n" + "=" * 70)
    print("CASE 3 — safe fallback (disambiguation could not resolve signs)")
    print("=" * 70)
    disambig_output_3 = {
        "source": "parent_reported_voice",
        "signs": {},
        "safe_fallback_message": "please get the baby checked",
    }
    result_3 = agent.handle({}, disambig_output_3, household_id="HH-3099")
    print(json.dumps(result_3.__dict__, indent=2))

    print("\n" + "=" * 70)
    print("CASE 4 — sign-specificity regression test (same category, different signs)")
    print("=" * 70)
    disambig_output_4 = {
        "source": "parent_reported_voice",
        "signs": {"feeding": "not_feeding_well"},  
        "safe_fallback_message": None,
    }
    result_4 = agent.handle(risk_output_1, disambig_output_4, household_id="HH-4055")
    print(json.dumps(result_4.__dict__, indent=2))
    assert result_1.reply_text != result_4.reply_text, (
        "Case 1 and Case 4 hit the same rule category but different signs -- "
        "reply text must differ, or the sign-specificity fix has regressed"
    )
    print("\nPASSED: Case 1 and Case 4 (same category, different signs) produce distinct replies")