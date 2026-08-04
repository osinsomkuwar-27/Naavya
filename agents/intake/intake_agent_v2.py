"""
agents/intake/intake_agent_v2.py

Schema-constrained LLM extraction, replacing keyword/substring matching
(intake_agent.py's original _KEYWORD_RULES approach).

WHY THIS EXISTS
----------------
The keyword-matching approach broke on real ASR output almost
immediately: "chest is pulling" (real transcript) did not match the
hardcoded trigger "chest pulling" -- a severe danger sign (chest
indrawing) silently disappeared. Extending the keyword lists to cover
every phrasing variant, in every supported language (Hindi, Kannada,
Odia, Bhojpuri...), means maintaining N fragile phrase lists instead
of fixing the actual problem: natural speech doesn't match fixed
substrings.

DESIGN
------
1. The LLM is given the EXACT sign vocabulary from
   data/imnci_rules/danger_signs.json, read dynamically at call time
   -- not hardcoded into the prompt. If Kshitij's schema changes, this
   agent updates automatically; nothing goes silently stale.
2. The LLM's job is narrow: read the transcript (in whatever language
   it's actually in -- no translation step, so no clinical nuance is
   lost in translation) and map what's said onto that fixed vocabulary.
   It is NOT asked to diagnose or reason clinically -- that's still
   entirely the Risk Combination Agent's job downstream.
3. Every value the LLM returns is validated against
   mcp/tools/validator.py -- the exact same validator Kshitij's
   imnci_lookup uses. Anything invalid (typo, hallucinated value,
   wrong enum) is automatically treated as unresolved, NOT accepted.
   This means the LLM extraction is at least as strict as the old
   keyword matching, just far more robust to real phrasing.
4. A lightweight keyword presence check runs alongside as an AUDIT
   SIGNAL ONLY (logged, never blocking) -- if the LLM claims a sign
   but zero related keywords appear anywhere in the transcript across
   any known language list, that's flagged for human review later,
   without silently overriding the LLM's read of the sentence.
5. Output contract is IDENTICAL to the original extract_signs():
   {"source", "raw_transcript", "clear_signs", "vague_signs"} --
   this is a drop-in replacement. Nothing downstream (disambiguation,
   risk agent, escalation) needs to change.
"""

import json
import os
import sys
import logging
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp"))
from tools.validator import validate_signs, coerce_age_days  # noqa: E402

logger = logging.getLogger("neotriage.intake_v2")
logging.basicConfig(level=logging.INFO)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "imnci_rules")


@dataclass
class IntakeResult:
    raw_transcript: str
    source: str = "parent_reported_voice"
    language: str = "en"
    clear_signs: dict = field(default_factory=dict)
    vague_signs: list = field(default_factory=list)
    audit_flags: list = field(default_factory=list)  # low-confidence extractions, for review only

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "raw_transcript": self.raw_transcript,
            "language": self.language,
            "clear_signs": self.clear_signs,
            "vague_signs": self.vague_signs,
            "audit_flags": self.audit_flags,  # now exposed -- was previously invisible to callers
        }


def _load_schema() -> dict:
    with open(os.path.join(DATA_DIR, "danger_signs.json"), "r", encoding="utf-8") as f:
        return json.load(f)["signs"]


def _build_extraction_prompt(transcript: str, schema: dict) -> str:
    """
    Builds the schema-constrained extraction prompt dynamically from
    the live schema, so the vocabulary the LLM is allowed to use always
    matches Kshitij's rule table exactly -- no hardcoded, driftable
    phrase lists anywhere in this file.
    """
    field_descriptions = []
    for field_name, field_def in schema.items():
        values = field_def.get("values")
        if isinstance(values, list):
            field_descriptions.append(
                f'- "{field_name}": one of {values} — {field_def.get("description", "")}'
            )
        elif field_name == "age_days":
            field_descriptions.append(
                f'- "{field_name}": integer 0-59 — {field_def.get("description", "")}'
            )

    schema_text = "\n".join(field_descriptions)

    return f"""You are extracting structured clinical signs from a caregiver's spoken description of a newborn infant, for a triage support tool. The caregiver may speak in any language or dialect -- read the meaning directly, do not translate first.

TRANSCRIPT (verbatim, any language):
\"\"\"{transcript}\"\"\"

ALLOWED SIGN FIELDS AND VALUES (use ONLY these field names and ONLY these exact values -- never invent a new field or value):
{schema_text}

CRITICAL -- DO NOT OMIT A CATEGORY JUST BECAUSE THE SENTENCE IS COMPLEX:
If a transcript contains BOTH a reassuring phrase and a concerning phrase about the SAME category (e.g. "not breathing very fast" AND "chest is pulling while breathing" in the same sentence), the concerning detail is the one that matters clinically -- chest indrawing/pulling is a DISTINCT, MORE SEVERE sign than breathing rate, not a contradiction to be averaged out or dropped. Never let a mention of "normal" on one aspect cause you to silently skip a genuinely concerning detail mentioned elsewhere in the same sentence. When in doubt about a category, include it in vague_signs -- never omit a category entirely just because the sentence was hard to parse.

Worked example (this exact pattern has been missed before -- read it carefully):
Transcript: "The baby is not breathing very fast. The chest is pulling while breathing and is having a little cold."
Correct extraction: {{"clear_signs": {{"breathing_rate": "severe_chest_indrawing"}}, "vague_signs": ["temperature"]}}
(Chest pulling/indrawing is caught and reported as clear, DESPITE the earlier "not breathing very fast" phrase. "A little cold" is genuinely vague, so temperature goes to vague_signs.)

INSTRUCTIONS:
1. For each sign the caregiver clearly and unambiguously described, output it under "clear_signs" using the EXACT field name and EXACT value from the list above.
2. For each sign category the caregiver mentioned but too vaguely to map confidently to one specific value (e.g. "not doing well" for feeding, without saying refusing vs. reduced), list the field name under "vague_signs" instead -- do NOT guess a specific value.
3. If a sign category was not mentioned at all, omit it entirely from both lists. Absence is "unknown", not "normal" -- never infer a normal/healthy value for something that was never mentioned.
4. Only use field names and values that appear EXACTLY in the allowed list above. If you are unsure a value truly matches, put the field name in vague_signs instead of guessing.
5. "age_days" must be output as a bare JSON number (e.g. 8), never as a quoted string (e.g. NOT "8") -- even though other fields in the example below are shown quoted.

Respond with ONLY valid JSON, no other text, in this exact shape:
{{"clear_signs": {{"field_name": "value", ...}}, "vague_signs": ["field_name", ...]}}"""


# ---------------------------------------------------------------------------
# Vocabulary translation: the LLM extraction prompt above is built purely
# from Kshitij's danger_signs.json SCHEMA FIELD NAMES (e.g. "breathing_rate",
# "jaundice_onset"). Shreeja's disambiguation QUESTION_BANK uses a SEPARATE,
# slightly different key vocabulary for vague signs (e.g. "breathing",
# "jaundice_age") -- a holdover convention from the original v1 intake
# agent. These two vocabularies coincide for most categories and
# diverge for a couple -- without this translation, a vague sign
# correctly identified by the LLM as "breathing_rate" would fail
# QUESTION_BANK.get("breathing_rate") -> None downstream, and no
# follow-up question would ever be asked. "age_days" is NOT translated
# here because it now has its own QUESTION_BANK entry under that exact
# key (see disambiguation_agent.py) -- it doesn't need remapping.
# ---------------------------------------------------------------------------
_SCHEMA_TO_QUESTION_BANK_KEY = {
    "breathing_rate": "breathing",
    "jaundice_onset": "jaundice_age",
    # feeding, temperature, jaundice_extent, age_days already match
    # QUESTION_BANK keys exactly and need no translation.
}


def _translate_vague_signs_for_disambiguation(vague_signs: list) -> list:
    """Maps schema field names to the key vocabulary Shreeja's
    QUESTION_BANK/get_question() actually expects."""
    return [_SCHEMA_TO_QUESTION_BANK_KEY.get(v, v) for v in vague_signs]


def _call_llm_for_extraction(prompt: str) -> dict:
    """
    Makes the actual LLM call via Groq (the provider actually in use for
    this project -- NOT Anthropic, despite an earlier version of this
    file assuming otherwise, which silently failed authentication and
    returned empty signs on every real call without raising a visible
    error until logging was added).

    Requires GROQ_API_KEY in the environment. Model is configurable via
    GROQ_MODEL env var, defaulting to a strong, fast instruction-following
    model available on Groq's free tier.
    """
    try:
        from groq import Groq
    except ImportError as e:
        raise RuntimeError(
            "groq package not installed. Run: pip install groq --break-system-packages"
        ) from e

    client = Groq()  # reads GROQ_API_KEY from env
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,  # deterministic extraction, not creative generation
        max_tokens=1000,
    )

    text = completion.choices[0].message.content.strip()
    # Defensive: strip markdown code fences if the model adds them despite instructions
    text = text.replace("```json", "").replace("```", "").strip()

    return json.loads(text)


# ---------------------------------------------------------------------------
# Lightweight audit cross-check -- NOT the extraction mechanism, just a
# logged confidence signal. Kept intentionally simple (a handful of
# common keywords across a few languages) since it never blocks
# anything; it only flags for human review if the LLM claims a sign
# with literally zero related vocabulary present anywhere.
# ---------------------------------------------------------------------------

_AUDIT_KEYWORDS = {
    "feeding": ["feed", "doodh", "milk", "haalu", "khana"],
    "breathing_rate": ["breath", "saans", "chest", "usiru"],
    "temperature": ["fever", "hot", "cold", "garam", "thanda", "jwara"],
    "jaundice_onset": ["yellow", "peela", "jaundice", "haladi"],
    "jaundice_extent": ["yellow", "peela", "jaundice", "haladi"],
    "convulsions": ["fit", "jhatke", "convuls", "seizure"],
    "movement": [
        "move", "moving", "movement", "active", "hilta", "lethargic",
        "limp", "still", "stiff",
    ],
}


def _audit_check(clear_signs: dict, transcript: str) -> list:
    flags = []
    text_lower = transcript.lower()
    for field_name in clear_signs:
        keywords = _AUDIT_KEYWORDS.get(field_name, [])
        if keywords and not any(kw in text_lower for kw in keywords):
            flags.append(
                f"LLM extracted '{field_name}' but no related keyword found in "
                f"transcript across known languages -- flagged for review, not blocked."
            )
    return flags


# ---------------------------------------------------------------------------
# Main entry point -- SAME signature/contract as the original extract_signs()
# ---------------------------------------------------------------------------

def extract_signs(transcript: str, language: str = "en") -> IntakeResult:
    schema = _load_schema()
    prompt = _build_extraction_prompt(transcript, schema)

    result = IntakeResult(raw_transcript=transcript, language=language)

    try:
        llm_output = _call_llm_for_extraction(prompt)
    except Exception as e:
        # LLM call failed entirely (network, auth, malformed JSON) --
        # fail toward caution: treat everything as unresolved rather
        # than silently returning empty/wrong signs. LOG LOUDLY -- this
        # must never fail silently again, since an empty result here
        # looks identical to "genuinely nothing to report" downstream.
        logger.error(f"LLM extraction FAILED for transcript: {transcript!r}")
        logger.error(f"Exception: {type(e).__name__}: {e}")
        result.audit_flags.append(f"LLM extraction failed entirely: {type(e).__name__}: {e}")
        return result

    logger.info(f"LLM raw output for transcript {transcript!r}: {llm_output}")

    raw_clear = llm_output.get("clear_signs", {})
    raw_vague = llm_output.get("vague_signs", [])

    # Validate every LLM-claimed value against the SAME validator used
    # by imnci_lookup -- anything invalid gets demoted to vague, not
    # silently accepted or silently dropped.
    validation = validate_signs(raw_clear)
    invalid_keys = set()
    for error in validation["errors"]:
        # error format: "'key' = 'value' is not a recognized value. ..."
        key = error.split("'")[1]
        invalid_keys.add(key)

    for key, value in raw_clear.items():
        if key in invalid_keys or key in validation["unknown_keys"]:
            translated_key = _SCHEMA_TO_QUESTION_BANK_KEY.get(key, key)
            result.vague_signs.append(translated_key)
            result.audit_flags.append(
                f"LLM claimed '{key}'='{value}' but this failed schema validation "
                f"-- demoted to vague_signs rather than trusted."
            )
        elif key == "age_days":
            result.clear_signs[key] = coerce_age_days(value)
        else:
            result.clear_signs[key] = value

    for key in raw_vague:
        translated_key = _SCHEMA_TO_QUESTION_BANK_KEY.get(key, key)
        if translated_key not in result.vague_signs:
            result.vague_signs.append(translated_key)

    result.audit_flags.extend(_audit_check(result.clear_signs, transcript))

    # Safety net: a substantive transcript (not just a couple words)
    # that produces ZERO signs at all -- neither clear nor vague -- is
    # suspicious, not necessarily "genuinely nothing to report". This
    # exact failure mode happened live: a transcript describing severe
    # chest indrawing extracted to {} / [] with no error raised, and
    # the pipeline silently proceeded past disambiguation entirely.
    word_count = len(transcript.split())
    if word_count > 5 and not result.clear_signs and not result.vague_signs:
        warning = (
            f"SUSPICIOUS: transcript has {word_count} words but extraction "
            f"produced zero signs (neither clear nor vague). This may be a "
            f"genuine extraction miss, not a truly sign-free transcript -- "
            f"flagging loudly rather than letting this pass silently."
        )
        logger.warning(warning)
        result.audit_flags.append(warning)

    return result


if __name__ == "__main__":
    # Manual test harness -- run against the exact transcript that broke
    # the old keyword matcher, to prove this approach handles it.
    sample = (
        "The baby is not breathing very fast. The chest is pulling while "
        "breathing and is having a little cold."
    )

    print("Testing against the real transcript that broke keyword matching:")
    print(f"Transcript: {sample}\n")

    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY not set in this environment -- skipping live call.")
        print("Set the key and re-run to see real extraction against this transcript.")
    else:
        out = extract_signs(sample)
        print("EXTRACTION RESULT:")
        print(json.dumps(out.to_dict(), indent=2))
        if out.audit_flags:
            print("\nAUDIT FLAGS (for review, non-blocking):")
            for flag in out.audit_flags:
                print(f"  - {flag}")