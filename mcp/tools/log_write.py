"""
log_write.py

Writes anonymized interaction records to a local SQLite database. No
personal identifiers (name, phone number, exact address) are ever
accepted or stored — this keeps the tool compliant with the hackathon's
data-ethics requirement (no personal data without consent) without
needing any consent workflow at all, since nothing personal is captured.

This is what closes the "did the referral actually happen" loop that
currently just disappears into a paper register.
"""

import sqlite3
import os
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "db", "naavya_log.db")
_FORBIDDEN_KEYS = {"name", "phone", "phone_number", "address", "mother_name", "father_name"}


def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interaction_log (
            id TEXT PRIMARY KEY,
            timestamp_utc TEXT NOT NULL,
            source TEXT NOT NULL,
            language TEXT,
            signs_json TEXT NOT NULL,
            highest_urgency TEXT NOT NULL,
            matched_rule_ids TEXT NOT NULL,
            referral_sent INTEGER NOT NULL DEFAULT 0,
            followup_completed INTEGER NOT NULL DEFAULT 0,
            followup_notes TEXT
        )
    """)
    return conn


def log_write(signs: dict, lookup_result: dict, source: str, language: Optional[str] = None) -> dict:
    """
    Args:
        signs: the structured signs that were classified (anonymized —
            no personal identifiers should ever be in this dict)
        lookup_result: output of imnci_lookup()
        source: "asha_reported" or "parent_reported"
        language: the language the interaction happened in, e.g. "kannada"

    Returns:
        { "record_id": str, "written": bool, "error": str | None }
    """
    for key in signs:
        if key.lower() in _FORBIDDEN_KEYS:
            return {
                "record_id": None,
                "written": False,
                "error": (
                    f"Refused to log: forbidden personal-identifier key "
                    f"'{key}' found in signs. Remove it before logging."
                ),
            }

    record_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    urgency = lookup_result.get("highest_urgency", "unknown")
    rule_ids = json.dumps(lookup_result.get("matched_rule_ids", []))
    referral_sent = 1 if urgency == "refer_now" else 0

    try:
        conn = _get_connection()
        conn.execute(
            """INSERT INTO interaction_log
               (id, timestamp_utc, source, language, signs_json,
                highest_urgency, matched_rule_ids, referral_sent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (record_id, timestamp, source, language, json.dumps(signs),
             urgency, rule_ids, referral_sent),
        )
        conn.commit()
        conn.close()
        return {"record_id": record_id, "written": True, "error": None}
    except Exception as e:
        return {"record_id": None, "written": False, "error": str(e)}


def mark_followup(record_id: str, completed: bool, notes: str = "") -> dict:
    """Updates a record once the ASHA/team confirms whether the referral
    was actually acted on — this is the loop-closing piece."""
    try:
        conn = _get_connection()
        conn.execute(
            "UPDATE interaction_log SET followup_completed = ?, followup_notes = ? WHERE id = ?",
            (1 if completed else 0, notes, record_id),
        )
        conn.commit()
        rows_affected = conn.total_changes
        conn.close()
        return {"updated": rows_affected > 0, "error": None}
    except Exception as e:
        return {"updated": False, "error": str(e)}