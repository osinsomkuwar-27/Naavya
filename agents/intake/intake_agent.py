"""
agents/intake/intake_agent.py
Owner: Soham

Takes a raw transcript (from asr/transcribe.py) and extracts candidate
IMNCI danger signs from free-form speech.

CONTRACT (matches downstream agents exactly -- do not change field
names without updating Shreeja's disambiguation_agent.py and Kshitij's
risk_agent.py):

  - "clear_signs": dict of {field_name: value} where field_name and
    value come DIRECTLY from Kshitij's data/imnci_rules/danger_signs.json
    vocabulary (e.g. {"feeding": "not_feeding_well"}). Only include a
    sign here if the transcript gave an unambiguous, mappable answer.

  - "vague_signs": list of sign KEYS (not field names) that matches
    Shreeja's QUESTION_BANK in agents/disambiguation/disambiguation_agent.py:
    "feeding", "temperature", "breathing", "jaundice_extent", "jaundice_age".
    Use this when the mother mentioned a symptom category but too
    vaguely to map to a value ourselves -- e.g. "he's not doing well"
    for feeding. Shreeja's agent asks a targeted follow-up for each key
    in this list.

  - Anything not detected at all (not mentioned) is simply absent from
    both dicts/lists -- absence is not "normal", it's "unknown", and
    downstream agents should treat it that way.

Scope note (per team's Round 1 decision to cover the 3 highest-mortality
combinations first): this PoC focuses extraction on feeding, breathing,
temperature, plus convulsions and movement since those complete the
"bacterial_infection_severe" rule Kshitij's table checks first. Jaundice
detection is included because Shreeja's disambiguation flow already
covers it. Extend _KEYWORD_RULES to add more signs later -- the
contract above does not change.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IntakeResult:
    raw_transcript: str
    source: str = "parent_reported_voice"
    clear_signs: dict = field(default_factory=dict)
    vague_signs: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "raw_transcript": self.raw_transcript,
            "clear_signs": self.clear_signs,
            "vague_signs": self.vague_signs,
        }


# ---------------------------------------------------------------------------
# Rule-based extraction. Kept rule-based (not an LLM call) deliberately --
# matches Shreeja's interpret_answer() philosophy: auditable and testable
# for a hackathon demo, not a black box. Each rule maps transcript
# keywords to EITHER a clear Kshitij-schema value, or flags the sign key
# as vague for Shreeja's follow-up questions.
# ---------------------------------------------------------------------------

_KEYWORD_RULES = {
    # --- feeding ---
    "feeding": {
        "clear_map": {
            "not able to feed": "not_able_to_feed_at_all",
            "won't feed": "not_able_to_feed_at_all",
            "wont feed": "not_able_to_feed_at_all",
            "refusing to feed": "not_able_to_feed_at_all",
            "stopped feeding": "not_able_to_feed_at_all",
            "feeding normally": "feeding_normally",
            "feeding fine": "feeding_normally",
            "feeding well": "feeding_normally",
        },
        "vague_triggers": [
            "not feeding well", "not feeding properly", "doodh nahi",
            "not eating well", "feeding less", "not drinking milk",
            "not feeding", "feeding problem",
        ],
        "target_field": "feeding",
    },
    # --- temperature ---
    "temperature": {
        "clear_map": {
            "very cold": "low_temp_below_35_5C_or_cold_to_touch",
            "feels cold": "low_temp_below_35_5C_or_cold_to_touch",
            "hands cold": "low_temp_below_35_5C_or_cold_to_touch",
            "normal temperature": "normal",
            "no fever": "normal",
            "not hot": "normal",
            "not cold": "normal",
        },
        "vague_triggers": [
            "fever", "hot", "warm", "garam", "temperature", "sweating",
            "cold", "thanda",
        ],
        "target_field": "temperature",
    },
    # --- breathing ---
    "breathing": {
        "clear_map": {
            "breathing normally": "normal",
            "breathing fine": "normal",
            "no breathing problem": "normal",
        },
        "vague_triggers": [
            "breathing fast", "breathing hard", "breathing problem",
            "chest pulling", "chest indrawing", "saans", "grunting",
            "breathless", "hard to breathe",
        ],
        "target_field": "breathing_rate",
    },
    # --- convulsions (kept clear-only -- urgent + usually unambiguous
    # in how it's described; no vague-follow-up defined by Shreeja yet) ---
    "convulsions": {
        "clear_map": {
            "convulsing": "convulsing_now",
            "convulsion": "convulsing_now",
            "fits": "convulsing_now",
            "seizure": "convulsing_now",
            "jhatke": "convulsing_now",
            "shaking uncontrollably": "convulsing_now",
            "had a convulsion": "had_convulsions",
            "no convulsions": "none",
            "no fits": "none",
        },
        "vague_triggers": [],
        "target_field": "convulsions",
    },
    # --- movement ---
    "movement": {
        "clear_map": {
            "not moving at all": "no_movement_at_all",
            "won't move": "no_movement_at_all",
            "limp": "no_movement_at_all",
            "only moves when i touch": "moves_only_when_stimulated",
            "only moves when touched": "moves_only_when_stimulated",
            "moving normally": "moves_on_own",
            "moving fine": "moves_on_own",
            "active": "moves_on_own",
        },
        "vague_triggers": ["not moving much", "less active", "lethargic", "sluggish"],
        "target_field": "movement",
    },
    # --- jaundice extent (Shreeja's disambiguation key: jaundice_extent) ---
    "jaundice_extent": {
        "clear_map": {},  # extent almost always needs the follow-up question
        "vague_triggers": ["yellow", "jaundice", "peela", "yellowish"],
        "target_field": "jaundice_extent",
    },
    # --- jaundice age (Shreeja's disambiguation key: jaundice_age) ---
    # Only flagged vague if jaundice was mentioned at all -- resolved
    # together with jaundice_extent in one disambiguation pass.
    "jaundice_age": {
        "clear_map": {},
        "vague_triggers": ["yellow", "jaundice", "peela", "yellowish"],
        "target_field": "jaundice_onset",
    },
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def extract_signs(transcript: str) -> IntakeResult:
    """
    Main entry point. Extracts candidate danger signs from a raw
    transcript string.

    NOTE: this PoC operates on the transcript AFTER translation/ASR to
    English-equivalent phrasing or transliterated Hindi keywords, per
    the Round 1 single-language scope decision. If Soham/Kshitij decide
    to keep the transcript in the native script instead of
    transliterating, _KEYWORD_RULES needs matching native-script
    keyword lists -- flagging this as a Day 1 scope decision, not
    silently assuming.
    """
    text = _normalize(transcript)
    result = IntakeResult(raw_transcript=transcript)

    seen_vague_keys = set()

    for rule_key, rule in _KEYWORD_RULES.items():
        target_field = rule["target_field"]

        # Combine clear and vague phrases into one ranked list, longest
        # phrase first. Longest-match-wins avoids false positives where
        # a short generic trigger (e.g. "fever") is a substring of a
        # more specific negated phrase (e.g. "no fever" -> clear/normal)
        # or vice versa (e.g. "feeding well" inside "not feeding well"
        # -> should resolve as vague, not clear).
        candidates = [
            (phrase, "clear", value) for phrase, value in rule["clear_map"].items()
        ] + [
            (phrase, "vague", None) for phrase in rule["vague_triggers"]
        ]
        candidates.sort(key=lambda c: len(c[0]), reverse=True)

        for phrase, kind, value in candidates:
            if phrase in text:
                if kind == "clear":
                    result.clear_signs[target_field] = value
                else:
                    if rule_key not in seen_vague_keys:
                        result.vague_signs.append(rule_key)
                        seen_vague_keys.add(rule_key)
                break

    return result


if __name__ == "__main__":
    # Manual test harness -- mirrors the example in the pitch doc.
    import json

    sample = "Bachcha subah se doodh nahi pi raha aur usko fever bhi hai"
    # Transliterated/keyword-normalized stand-in for the Hindi example,
    # since this PoC's keyword rules are English/transliterated for now:
    sample_normalized = (
        "baby has not been feeding since morning, not feeding well, "
        "and also has fever"
    )

    out = extract_signs(sample_normalized)
    print("INTAKE OUTPUT FOR DISAMBIGUATION AGENT:")
    print(json.dumps(out.to_dict(), indent=2))