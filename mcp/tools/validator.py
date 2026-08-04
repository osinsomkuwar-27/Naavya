"""
validator.py

Validates a structured signs dict against danger_signs.json BEFORE it
reaches the rule engine. This exists because imnci_lookup previously
trusted its input silently — a typo'd key or an invalid value would
just be ignored by the matcher rather than flagged, which is dangerous
for a clinical decision tool. Fail loud, not silent.
"""

import json
import os
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "imnci_rules")


def _load_schema() -> dict:
    path = os.path.join(DATA_DIR, "danger_signs.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["signs"]


_SCHEMA = _load_schema()


class ValidationError(Exception):
    """Raised when signs input doesn't match the known schema."""
    pass


def coerce_age_days(value) -> Optional[int]:
    """
    Normalizes an age_days value that may arrive as a real int, a
    numeric string ('8'), or occasionally a float (8.0), depending on
    how the LLM formatted its JSON output. LLMs are not perfectly
    type-strict even when the prompt explicitly says "integer" -- the
    extraction prompt's own example shows every field as a quoted JSON
    string, so age_days frequently comes back as "8" rather than 8.
    A genuinely correct age must not be rejected just because of that.

    Returns a plain int in [0, 59] if the value is valid, otherwise None.

    Deliberately excludes bool: isinstance(True, int) is True in
    Python, so without this explicit guard a stray boolean would
    silently coerce to age_days=1 or age_days=0.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        age = value
    elif isinstance(value, float) and value.is_integer():
        age = int(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped.lstrip("-").isdigit():
            return None
        age = int(stripped)
    else:
        return None

    if not (0 <= age <= 59):
        return None
    return age


def validate_signs(signs: dict) -> dict:
    """
    Checks every key in `signs` against danger_signs.json.
    Returns {"valid": bool, "errors": [...], "unknown_keys": [...], "warnings": [...]}

    Does NOT raise by default — callers decide whether to hard-fail or
    proceed with a warning, since a partially-valid input (e.g. one typo
    among ten correct signs) may still be usable if the agent can recover
    by asking a follow-up question rather than discarding everything.
    """
    errors = []
    warnings = []
    unknown_keys = []

    for key, value in signs.items():
        if key not in _SCHEMA:
            unknown_keys.append(key)
            continue

        schema_entry = _SCHEMA[key]
        allowed_values = schema_entry.get("values")

        if isinstance(allowed_values, str):
            if key == "age_days":
                if coerce_age_days(value) is None:
                    errors.append(
                        f"'{key}' must be an integer 0-59, got: {value!r}"
                    )
            continue

        if isinstance(allowed_values, list) and value not in allowed_values:
            errors.append(
                f"'{key}' = {value!r} is not a recognized value. "
                f"Expected one of: {allowed_values}"
            )

    if unknown_keys:
        warnings.append(
            f"Unknown sign keys (not in schema, ignored by rule engine): {unknown_keys}"
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "unknown_keys": unknown_keys,
        "warnings": warnings,
    }


def validate_signs_strict(signs: dict) -> None:
    """Raises ValidationError if any sign value is invalid. Use this when
    you want a hard failure rather than a warning — e.g. before logging
    a record, or in automated tests."""
    result = validate_signs(signs)
    if not result["valid"]:
        raise ValidationError("; ".join(result["errors"]))