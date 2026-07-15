from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Vagueness(str, Enum):
    CLEAR = "clear"
    VAGUE = "vague"
    UNRESOLVED = "unresolved"  # stayed vague after max attempts


MAX_DISAMBIGUATION_ROUNDS = 3

SAFE_FALLBACK_MESSAGE = (
    "I'm not fully sure yet. To be safe, please get the baby checked by "
    "your ASHA worker or the nearest health facility today."
)


# ---------------------------------------------------------------------------
# Question bank: one entry per IMNCI sign category that can arrive "vague"
# from free-speech intake. Each entry maps a parent-friendly question to the
# structured values it can resolve to (values match Kshitij's schema).
# ---------------------------------------------------------------------------

QUESTION_BANK = {
    "feeding": {
        "question": (
            "When you say the baby isn't feeding well — is the baby "
            "refusing to feed completely, or feeding but for a much "
            "shorter time than usual, or feeding but seeming too weak or "
            "sleepy to suck properly?"
        ),
        "answer_map": {
            "refusing": "not_able_to_feed_at_all",
            "not at all": "not_able_to_feed_at_all",
            "won't feed": "not_able_to_feed_at_all",
            "shorter": "not_feeding_well",
            "less": "not_feeding_well",
            "weak": "not_feeding_well",
            "sleepy": "not_feeding_well",
            "normal": "feeding_normally",
            "fine": "feeding_normally",
        },
        "target_field": "feeding",
    },
    "temperature": {
        "question": (
            "Does the baby's body or skin feel warmer than usual to "
            "touch, or have you noticed sweating — or does the baby feel "
            "unusually cold, especially the hands and feet?"
        ),
        "answer_map": {
            "warm": "fever_37_5C_or_above_or_hot_to_touch",
            "hot": "fever_37_5C_or_above_or_hot_to_touch",
            "sweat": "fever_37_5C_or_above_or_hot_to_touch",
            "cold": "low_temp_below_35_5C_or_cold_to_touch",
            "normal": "normal",
            "fine": "normal",
        },
        "target_field": "temperature",
    },
    "breathing": {
        "question": (
            "When the baby breathes, do you notice the chest pulling in "
            "with each breath, or breathing much faster than normal, or "
            "any grunting sound?"
        ),
        "answer_map": {
            "pulling": "severe_chest_indrawing",
            "indrawing": "severe_chest_indrawing",
            "fast": "fast_breathing",
            "quick": "fast_breathing",
            "grunt": "fast_breathing",
            "normal": "normal",
            "fine": "normal",
        },
        "target_field": "breathing_rate",
    },
    "jaundice_extent": {
        "question": (
            "Is the yellow colour only on the face, or has it spread down "
            "to the arms and legs (palms and soles)?"
        ),
        "answer_map": {
            "face": "face_or_body_only",
            "body": "face_or_body_only",
            "palms": "palms_or_soles_yellow",
            "soles": "palms_or_soles_yellow",
            "hands": "palms_or_soles_yellow",
            "feet": "palms_or_soles_yellow",
            "spread": "palms_or_soles_yellow",
        },
        "target_field": "jaundice_extent",
    },
    "jaundice_age": {
        # Critical follow-up per the rule-table review: age >=14 days
        # with jaundice present must be escalated regardless of extent.
        "question": (
            "How many days old is the baby today, and roughly how many "
            "days ago did you first notice the yellow colour?"
        ),
        "answer_map": {},  # parsed numerically, not by keyword — see below
        "target_field": "jaundice_onset",
    },
}


@dataclass
class DisambiguationResult:
    resolved_signs: dict = field(default_factory=dict)
    unresolved_signs: list = field(default_factory=list)
    safe_fallback_triggered: bool = False
    source: str = "parent_reported_voice"


class DisambiguationAgent:
    """
    Conversational disambiguation over one or more vague candidate signs
    coming from the Intake Agent. Call `resolve_sign()` per vague sign;
    it yields questions and accepts answers until resolved or the
    guardrail limit is hit.
    """

    def __init__(self, language: str = "en"):
        self.language = language

    def get_question(self, sign_key: str) -> Optional[str]:
        entry = QUESTION_BANK.get(sign_key)
        return entry["question"] if entry else None

    def interpret_answer(self, sign_key: str, answer_text: str) -> Optional[str]:
        """Very simple keyword matcher for the PoC. In production this
        step is where an LLM call or a proper NLU model would sit —
        kept rule-based here so behaviour is auditable and testable."""
        entry = QUESTION_BANK.get(sign_key)
        if not entry:
            return None

        answer_lower = answer_text.lower()

        if sign_key == "jaundice_age":
            return self._parse_age_answer(answer_text)

        for keyword, value in entry["answer_map"].items():
            if keyword in answer_lower:
                return value
        return None

    def _parse_age_answer(self, answer_text: str) -> Optional[dict]:
        """Extract baby's current age in days and jaundice onset day from
        free text like 'baby is 16 days old, saw it about 3 days ago'."""
        import re

        numbers = [int(n) for n in re.findall(r"\d+", answer_text)]
        if not numbers:
            return None
        current_age_days = numbers[0]
        onset_days_ago = numbers[1] if len(numbers) > 1 else 0
        onset_day = max(current_age_days - onset_days_ago, 0)

        # Derive the categorical value Kshitij's rules actually check
        # (jaundice_onset: onset_before_24_hours / onset_after_24_hours).
        # onset_day is the baby's age in days when jaundice first appeared.
        if onset_day < 1:
            jaundice_onset = "onset_before_24_hours"
        else:
            jaundice_onset = "onset_after_24_hours"

        return {
            "age_days": current_age_days,
            "jaundice_onset_day": onset_day,
            "jaundice_onset": jaundice_onset,
            # Matches the fixed severe-jaundice rule: age >= 14 days
            # with jaundice present -> must escalate.
            "age_14_days_or_more_with_jaundice": current_age_days >= 14,
        }

    def resolve_sign(self, sign_key: str, get_answer_fn) -> DisambiguationResult:
        """
        Drives up to MAX_DISAMBIGUATION_ROUNDS question/answer cycles for
        a single vague sign. `get_answer_fn` is a callable(question) ->
        answer_text, so this stays decoupled from the actual transport
        (voice/WhatsApp/web text box).
        """
        result = DisambiguationResult()
        entry = QUESTION_BANK.get(sign_key)
        if not entry:
            result.unresolved_signs.append(sign_key)
            return result

        for attempt in range(MAX_DISAMBIGUATION_ROUNDS):
            question = entry["question"]
            answer_text = get_answer_fn(question)
            parsed = self.interpret_answer(sign_key, answer_text)

            if parsed is not None:
                if sign_key == "jaundice_age":
                    result.resolved_signs.update(parsed)
                else:
                    result.resolved_signs[entry["target_field"]] = parsed
                return result

        # Guardrail: stayed ambiguous after max attempts.
        result.unresolved_signs.append(sign_key)
        result.safe_fallback_triggered = True
        return result

    def resolve_all(self, vague_signs: list, get_answer_fn) -> DisambiguationResult:
        """Resolve multiple vague signs from one Intake Agent output,
        merging into a single structured object for the Risk Combination
        Agent."""
        merged = DisambiguationResult()
        for sign_key in vague_signs:
            single = self.resolve_sign(sign_key, get_answer_fn)
            merged.resolved_signs.update(single.resolved_signs)
            merged.unresolved_signs.extend(single.unresolved_signs)
            if single.safe_fallback_triggered:
                merged.safe_fallback_triggered = True
        return merged

    def build_output(self, merged: DisambiguationResult) -> dict:
        """Final structured object handed to the Risk Combination Agent."""
        return {
            "source": merged.source,
            "confidence": "probed" if not merged.unresolved_signs else "unresolved",
            "signs": merged.resolved_signs,
            "unresolved_signs": merged.unresolved_signs,
            "safe_fallback_message": (
                SAFE_FALLBACK_MESSAGE if merged.safe_fallback_triggered else None
            ),
        }

    def process_intake(self, intake_output: dict, get_answer_fn) -> dict:
        """
        Full entry point matching the Intake Agent's output contract:
        {"source", "raw_transcript", "clear_signs", "vague_signs"}.

        Resolves vague_signs via disambiguation, then MERGES in
        clear_signs (already-confident signs from the Intake Agent) so
        nothing he already extracted gets dropped. clear_signs values
        win on overlap (they came from an unambiguous transcript match;
        disambiguation only runs on signs he explicitly flagged vague,
        so overlap shouldn't normally happen -- but clear_signs is
        trusted first if it ever does).
        """
        vague_signs = intake_output.get("vague_signs", [])
        clear_signs = intake_output.get("clear_signs", {})

        merged = self.resolve_all(vague_signs, get_answer_fn)
        merged.source = intake_output.get("source", merged.source)

        output = self.build_output(merged)
        # clear_signs first, then disambiguated signs layered on top --
        # but clear_signs wins if a key ever collides.
        combined_signs = {**output["signs"], **clear_signs}
        output["signs"] = combined_signs
        output["raw_transcript"] = intake_output.get("raw_transcript")
        return output


# ---------------------------------------------------------------------------
# Manual test harness — run this file directly to try it with text input
# before wiring in real ASR/voice. Mirrors Step 3 of the build plan:
# "Test with text input first."
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    agent = DisambiguationAgent(language="en")

    # Simulated case: Kannada jaundice example from the pitch doc, but
    # with age pushed to 16 days to test the fixed severe-jaundice path.
    scripted_answers = {
        QUESTION_BANK["jaundice_extent"]["question"]: "Only on the face",
        QUESTION_BANK["jaundice_age"]["question"]: "baby is 16 days old, noticed the yellow about 6 days ago",
    }

    def mock_get_answer(question: str) -> str:
        print(f"AGENT ASKS: {question}")
        answer = scripted_answers.get(question, "not sure")
        print(f"PARENT ANSWERS: {answer}\n")
        return answer

    vague_signs = ["jaundice_extent", "jaundice_age"]
    merged = agent.resolve_all(vague_signs, mock_get_answer)
    output = agent.build_output(merged)

    import json
    print("STRUCTURED OUTPUT FOR RISK COMBINATION AGENT:")
    print(json.dumps(output, indent=2))

    print("\n" + "=" * 70)
    print("TEST 2 -- full process_intake() using the real Intake Agent output shape")
    print("=" * 70)

    # Matches agents/intake/intake_agent.py's sample transcript output exactly:
    # "baby has not been feeding since morning, not feeding well, and
    # also has fever" -> clear_signs empty, vague_signs=["feeding","temperature"]
    intake_output_sample = {
        "source": "parent_reported_voice",
        "raw_transcript": (
            "baby has not been feeding since morning, not feeding well, "
            "and also has fever"
        ),
        "clear_signs": {"movement": "moves_on_own"},  # e.g. he also caught this clearly
        "vague_signs": ["feeding", "temperature"],
    }

    scripted_answers_2 = {
        QUESTION_BANK["feeding"]["question"]: "not feeding at all, refusing completely",
        QUESTION_BANK["temperature"]["question"]: "feels very warm and sweaty",
    }

    def mock_get_answer_2(question: str) -> str:
        print(f"AGENT ASKS: {question}")
        answer = scripted_answers_2.get(question, "not sure")
        print(f"PARENT ANSWERS: {answer}\n")
        return answer

    final_output = agent.process_intake(intake_output_sample, mock_get_answer_2)
    print("FINAL MERGED OUTPUT (clear_signs + disambiguated signs):")
    print(json.dumps(final_output, indent=2))