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
    asha_alert_sent: bool = False
    asha_alert_text: Optional[str] = None
    log_entry: dict = field(default_factory=dict)
    follow_up_date: Optional[str] = None


class EscalationAgent:
    def __init__(self, language: str = "en"):
        self.language = language

    def build_reply(self, risk_output: dict) -> str:
        """
        risk_output is expected to come from the Risk Combination Agent,
        shaped roughly like one matched rule from combination_rules.json:
        {
          "classification": "severe_jaundice",
          "urgency": "refer_now",
          "action_summary": "...",
        }
        """
        urgency = risk_output["urgency"]
        template = TEMPLATES.get(urgency, SAFE_FALLBACK_TEMPLATE)
        return template.format(
            classification=risk_output.get("classification", "this condition").replace("_", " "),
            action_summary=risk_output.get("action_summary", ""),
        )

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
                asha_alert_sent=asha_alert_sent,
                asha_alert_text=asha_alert_text,
                log_entry=log_entry,
                follow_up_date=None,
            )

        reply_text = self.build_reply(risk_output)
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
            asha_alert_sent=asha_alert_sent,
            asha_alert_text=asha_alert_text,
            log_entry=log_entry,
            follow_up_date=follow_up_date,
        )


# ---------------------------------------------------------------------------
# Manual test harness — three scenarios matching the ones already in the
# pitch doc: refer_now (Bihar), reassure (Karnataka jaundice), and the
# safe-fallback guardrail case.
# ---------------------------------------------------------------------------

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