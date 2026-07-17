"""
agents/intake/intake_agent_v2.py
Owner: Soham

LLM-based replacement for the keyword-matching extract_signs() in
intake_agent.py. Uses Groq (fast-inference API, hosts Llama/Mixtral
models) via the OpenAI-compatible SDK, per Kshitij's direction
(Anthropic -> switched to Groq/Gemini; this file uses Groq).

WHY THIS EXISTS (see intake_agent.py's known limitation):
The v1 keyword matcher only catches literal substrings -- "chest is
pulling in" doesn't match the hardcoded phrase "chest pulling", so a
refer_now-level danger sign (severe_chest_indrawing) silently gets
missed. It also has near-zero real multi-language support: a few
transliterated Hindi keywords, nothing else. An LLM with the sign
vocabulary given in-context handles paraphrasing and other languages
without needing hand-written phrase lists for every dialect variant.

CONTRACT: identical to v1's extract_signs()/IntakeResult -- same
clear_signs/vague_signs shape, same field names/values from
data/imnci_rules/danger_signs.json. Downstream code (assess.py,
webhook.py, Shreeja's disambiguation agent) does not need to change
when this replaces v1, only the import line does.

Adds one field vs v1: `language` (ISO code from Whisper's detected
language) -- Shreeja's TTS/escalation flow reads this to reply in the
mother's own language instead of defaulting to English.

FAILOVER: if the Groq API call fails or times out (network issue,
rate limit, demo-day wifi problems), this falls back to v1's
keyword-based extract_signs() rather than erroring out -- a degraded
but working pipeline beats a crashed one on demo day.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

# Allow `python3 agents/intake/intake_agent_v2.py` to run directly --
# when a script is invoked this way, Python puts the script's own
# directory (agents/intake/) at sys.path[0], NOT the project root, so
# `from agents.intake.intake_agent import ...` (the fallback import
# below) fails with ModuleNotFoundError unless the root is added
# explicitly. Has no effect when this module is imported normally
# (e.g. from assess.py), since the root is already on sys.path then.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

_CLIENT = None


@dataclass
class IntakeResult:
    raw_transcript: str
    source: str = "parent_reported"
    language: str = "en"
    clear_signs: dict = field(default_factory=dict)
    vague_signs: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "language": self.language,
            "raw_transcript": self.raw_transcript,
            "clear_signs": self.clear_signs,
            "vague_signs": self.vague_signs,
        }


class IntakeExtractionError(Exception):
    pass


# ---------------------------------------------------------------------------
# Sign vocabulary given to the LLM in-context. Kept in sync manually with
# data/imnci_rules/danger_signs.json -- if Kshitij adds/renames a sign
# there, mirror it here too. (Extension idea for later: load this
# directly from the JSON file at import time instead of hardcoding, so
# the two can never drift -- flagging as a follow-up, not blocking.)
# ---------------------------------------------------------------------------

_SIGN_VOCABULARY = {
    "feeding": ["feeding_normally", "not_feeding_well", "not_able_to_feed_at_all"],
    "convulsions": ["none", "convulsing_now", "had_convulsions"],
    "breathing_rate": ["normal", "fast_breathing", "severe_chest_indrawing"],
    "temperature": [
        "normal",
        "fever_37_5C_or_above_or_hot_to_touch",
        "low_temp_below_35_5C_or_cold_to_touch",
    ],
    "movement": ["moves_on_own", "moves_only_when_stimulated", "no_movement_at_all"],
    "umbilicus": ["normal", "red_or_draining_pus"],
    "skin_pustules": ["absent", "few_localized", "ten_or_more_or_big_boil"],
    "nasal_flaring": ["absent", "present"],
    "grunting": ["absent", "present"],
    "bulging_fontanelle": ["absent", "present"],
    "jaundice_onset": ["no_jaundice", "onset_before_24_hours", "onset_after_24_hours"],
    "jaundice_extent": ["not_applicable", "face_or_body_only", "palms_or_soles_yellow"],
    "diarrhoea_present": ["no", "yes"],
}

# Sign keys Shreeja's QUESTION_BANK can currently disambiguate. Anything
# outside this set that comes back "vague" from the LLM still gets
# reported, but flag to Shreeja if new keys show up here that her
# disambiguation_agent.py doesn't have a question for yet.
_DISAMBIGUATABLE_KEYS = {"feeding", "temperature", "breathing", "jaundice_extent", "jaundice_age"}

# CRITICAL: the LLM reasons in danger_signs.json FIELD NAMES (matching
# _SIGN_VOCABULARY), but Shreeja's QUESTION_BANK uses different, shorter
# KEYS for two of them. Confirmed against her actual merged
# disambiguation_agent.py on feature/mcp -- QUESTION_BANK has "breathing"
# (not "breathing_rate") and "jaundice_age" (not "jaundice_onset").
# Without this translation, get_question()/resume_disambiguation() would
# silently return None / raise KeyError on those two signs.
_FIELD_NAME_TO_DISAMBIGUATION_KEY = {
    "breathing_rate": "breathing",
    "jaundice_onset": "jaundice_age",
    # feeding, temperature, jaundice_extent are identical in both --
    # no translation needed for those.
}

_SYSTEM_PROMPT = f"""You are a clinical intake assistant extracting newborn danger signs \
from a caregiver's free-form spoken description (transcribed from voice, possibly in \
Hindi, Marathi, Odia, or English, or mixed).

Valid signs and their allowed values (JSON):
{json.dumps(_SIGN_VOCABULARY, indent=2)}

Task: read the transcript and classify each sign that was mentioned into ONE of two buckets:

1. "clear_signs": the transcript gives enough detail to map DIRECTLY to one of the \
exact allowed values above. Only include a sign here if you are confident of the exact \
value -- do not guess.

2. "vague_signs": the caregiver mentioned this symptom category but too vaguely to map \
to a specific value (e.g. "not doing well", general distress language, or ambiguous \
phrasing). List only the sign KEY (e.g. "feeding"), not a value.

Rules:
- Do not include a sign in the output at all if it was never mentioned.
- Never invent or assume a sign that wasn't described.
- Handle paraphrasing, dialect, and any language -- do not require literal keyword matches.
- "chest pulling in", "chest going in and out hard", "chest sinking" etc. all map to \
breathing_rate: severe_chest_indrawing if described as such.
- Respond with ONLY valid JSON, no markdown fences, no explanation, in this exact shape:
{{"clear_signs": {{"<field>": "<value>", ...}}, "vague_signs": ["<sign_key>", ...]}}
"""


def _get_client():
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    if not GROQ_API_KEY:
        raise IntakeExtractionError(
            "GROQ_API_KEY is not set. Export it before running: "
            "export GROQ_API_KEY=your_key_here"
        )

    try:
        from openai import OpenAI
    except ImportError as e:
        raise IntakeExtractionError(
            "openai package not installed. Run: pip install openai --break-system-packages"
        ) from e

    _CLIENT = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    return _CLIENT


def _call_groq(transcript: str) -> dict:
    client = _get_client()

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Transcript: {transcript}"},
        ],
        temperature=0,  # deterministic classification, not creative generation
    )

    raw = response.choices[0].message.content.strip()
    # Strip markdown fences defensively, in case the model wraps the JSON
    # despite instructions not to.
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise IntakeExtractionError(f"Groq returned non-JSON output: {raw[:200]}") from e

    return parsed


def _validate_and_clean(parsed: dict) -> tuple[dict, list]:
    """Defensive validation -- never trust LLM output blindly. Drop any
    field/value the model hallucinated outside the known vocabulary."""
    clear_signs = {}
    for field_name, value in parsed.get("clear_signs", {}).items():
        if field_name in _SIGN_VOCABULARY and value in _SIGN_VOCABULARY[field_name]:
            clear_signs[field_name] = value
        # Silently drop anything that doesn't match the schema -- better
        # to under-report than to pass a hallucinated value downstream
        # into a clinical decision.

    raw_vague = parsed.get("vague_signs", [])
    translated = [
        _FIELD_NAME_TO_DISAMBIGUATION_KEY.get(key, key) for key in raw_vague
    ]
    vague_signs = [key for key in translated if key in _DISAMBIGUATABLE_KEYS]
    # De-duplicate, preserve order (translation can create duplicates,
    # e.g. if the LLM never actually collides here, but defensive anyway)
    seen = set()
    vague_signs = [k for k in vague_signs if not (k in seen or seen.add(k))]

    return clear_signs, vague_signs


def extract_signs(transcript: str, language: str = "en") -> IntakeResult:
    """
    Main entry point -- same signature contract as v1, plus the new
    `language` parameter (pass through Whisper's detected language from
    asr/transcribe.py's TranscriptionResult.language).
    """
    try:
        parsed = _call_groq(transcript)
        clear_signs, vague_signs = _validate_and_clean(parsed)

        return IntakeResult(
            raw_transcript=transcript,
            language=language,
            clear_signs=clear_signs,
            vague_signs=vague_signs,
        )

    except IntakeExtractionError as e:
        # Graceful degradation: fall back to v1's keyword matcher rather
        # than failing the whole /assess request. Demo-day network
        # issues or a missing API key shouldn't take the pipeline down.
        try:
            from agents.intake.intake_agent import extract_signs as extract_signs_v1
        except ImportError:
            raise IntakeExtractionError(
                f"Groq call failed ({e}) and v1 fallback unavailable."
            ) from e

        fallback_result = extract_signs_v1(transcript)
        return IntakeResult(
            raw_transcript=transcript,
            language=language,
            clear_signs=fallback_result.clear_signs,
            vague_signs=fallback_result.vague_signs,
        )


if __name__ == "__main__":
    # Test harness -- run against the case that broke v1.
    test_cases = [
        (
            "baby's chest is pulling in hard when she breathes, and she "
            "hasn't fed since this morning",
            "en",
            "EXPECTED: breathing_rate=severe_chest_indrawing (v1 returned {})",
        ),
        (
            "baby ka chest andar ki taraf dhas raha hai",
            "hi",
            "EXPECTED: breathing_rate=severe_chest_indrawing, pure Hindi, no English",
        ),
    ]

    for transcript, lang, note in test_cases:
        print(f"\n--- {note} ---")
        print(f"IN: {transcript}")
        try:
            result = extract_signs(transcript, language=lang)
            print(json.dumps(result.to_dict(), indent=2))
        except IntakeExtractionError as e:
            print(f"ERROR: {e}")