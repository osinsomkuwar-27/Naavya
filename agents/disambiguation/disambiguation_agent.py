from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import re


class Vagueness(str, Enum):
    CLEAR = "clear"
    VAGUE = "vague"
    UNRESOLVED = "unresolved"  # stayed vague after max attempts


MAX_DISAMBIGUATION_ROUNDS = 3

SAFE_FALLBACK_MESSAGE = (
    "I'm not fully sure yet. To be safe, please get the baby checked by "
    "your ASHA worker or the nearest health facility today."
)

_NEGATION_WORDS = re.compile(r"\b(not|no|n't|isn't|doesn't|wasn't|never|without)\b")
_NEGATION_LOOKBACK_CHARS = 20


def _is_negated(text: str, keyword: str) -> bool:
    idx = text.find(keyword)
    if idx == -1:
        return False
    window_start = max(0, idx - _NEGATION_LOOKBACK_CHARS)
    window = text[window_start:idx]
    return bool(_NEGATION_WORDS.search(window))


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
    "age_days": {
        "question": "How many days old is the baby today?",
        "answer_map": {},  
        "target_field": "age_days",
    },
    "movement": {
        "question": (
            "Is the baby moving normally on their own — arms, legs, "
            "turning the head — or does the baby only move when you "
            "touch or shake them gently, or not move at all?"
        ),
        "answer_map": {
            "only when": "moves_only_when_stimulated",
            "touch": "moves_only_when_stimulated",
            "shake": "moves_only_when_stimulated",
            "not move": "no_movement_at_all",
            "not moving": "no_movement_at_all",
            "limp": "no_movement_at_all",
            "normal": "moves_on_own",
            "fine": "moves_on_own",
            "active": "moves_on_own",
        },
        "target_field": "movement",
    },
    "hydration_signs": {
        "question": (
            "Does the baby seem unusually restless or irritable, do the "
            "eyes look sunken in, or if you gently pinch the skin on the "
            "belly does it stay pinched for a moment before going back?"
        ),
        "answer_map": {
            "restless": "restless_or_irritable",
            "irritable": "irritable_or_restless",
            "sunken": "sunken_eyes",
            "slow": "skin_pinch_goes_back_slowly",
            "stays": "skin_pinch_goes_back_slowly",
            "very slow": "skin_pinch_goes_back_very_slowly",
            "normal": "none",
            "fine": "none",
        },
        "target_field": "hydration_signs",
    },
}
_GENERIC_FALLBACK_TEMPLATE = (
    "Can you tell me a bit more about the baby's {sign_key}? "
    "Anything you've noticed, even if you're not sure it matters."
)
_MULTI_FIELD_SIGN_KEYS = {"jaundice_age"}


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

    def get_question(self, sign_key: str) -> str:
        """Guaranteed to never return None -- falls back to a generic
        prompt for any sign_key without a dedicated QUESTION_BANK entry,
        so a conversation can never go silent mid-flow regardless of
        what vague-sign vocabulary the intake agent produces."""
        entry = QUESTION_BANK.get(sign_key)
        if entry:
            return entry["question"]
        return _GENERIC_FALLBACK_TEMPLATE.format(sign_key=sign_key.replace("_", " "))

    def interpret_answer(self, sign_key: str, answer_text: str):
        """Very simple keyword matcher for the PoC. In production this
        step is where an LLM call or a proper NLU model would sit —
        kept rule-based here so behaviour is auditable and testable.

        Returns None if unresolved, a dict for multi-field sign_keys
        (see _MULTI_FIELD_SIGN_KEYS), or a scalar value otherwise."""
        entry = QUESTION_BANK.get(sign_key)
        if not entry:
            return None

        answer_lower = answer_text.lower()

        if sign_key == "jaundice_age":
            return self._parse_age_answer(answer_text)

        if sign_key == "age_days":
            return self._parse_plain_age_answer(answer_text)

        for keyword, value in entry["answer_map"].items():
            if keyword in answer_lower and not _is_negated(answer_lower, keyword):
                return value
        return None

    def _parse_age_answer(self, answer_text: str) -> Optional[dict]:
        """Extract baby's current age in days and jaundice onset day from
        free text like 'baby is 16 days old, saw it about 3 days ago'."""
        numbers = [int(n) for n in re.findall(r"\d+", answer_text)]
        if not numbers:
            return None
        current_age_days = numbers[0]
        onset_days_ago = numbers[1] if len(numbers) > 1 else 0
        onset_day = max(current_age_days - onset_days_ago, 0)

        return {
            "age_days": current_age_days,
            "jaundice_onset": (
                "onset_before_24_hours" if onset_day <= 1
                else "onset_after_24_hours"
            ),
        }

    def _parse_plain_age_answer(self, answer_text: str) -> Optional[int]:
        """Extract a plain day-count from free text like '8 days old' or
        'She is 8 days old.'. Returns None (unresolved -- ask again) if no
        number is found, or if the number falls outside the valid IMNCI
        'Sick Young Infant' range (0-59 days), since a wildly out-of-range
        value is more likely a misheard/mistyped answer than genuine data
        we should silently accept."""
        numbers = [int(n) for n in re.findall(r"\d+", answer_text)]
        if not numbers:
            return None
        age = numbers[0]
        if not (0 <= age <= 59):
            return None
        return age

    def resume_disambiguation(
        self, sign_key: str, answer_text: str,
        already_resolved: dict, already_unresolved: list,
        attempts_so_far: int,
    ) -> dict:
        """Called with ONE answer to ONE question, picks up where the
        conversation left off instead of looping inline. Soham's /assess
        endpoint calls this per HTTP request, passing in saved state from
        his pending_disambiguation table (conversation_id-keyed)."""
        parsed = self.interpret_answer(sign_key, answer_text)
        if parsed is not None:
            if sign_key in _MULTI_FIELD_SIGN_KEYS:
                already_resolved.update(parsed)
            else:
                already_resolved[QUESTION_BANK[sign_key]['target_field']] = parsed
            return {"status": "resolved", "resolved_signs": already_resolved}
        if attempts_so_far + 1 >= MAX_DISAMBIGUATION_ROUNDS:
            already_unresolved.append(sign_key)
            return {"status": "unresolved", "fallback": SAFE_FALLBACK_MESSAGE}
        return {"status": "ask_again", "question": self.get_question(sign_key)}

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
                if sign_key in _MULTI_FIELD_SIGN_KEYS:
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
        output["language"] = intake_output.get("language", "en")
        return output