"""
backend/api/session/store.py
Owner: Soham

Session state for multi-turn disambiguation over plain HTTP. A single
/assess call can't block and wait for a follow-up answer (WhatsApp
messages and web requests are separate round-trips), so this stores
"we're mid-conversation with this household" state keyed by
conversation_id, matching the schema Shreeja needs for
resume_disambiguation().

CURRENT BACKEND: in-memory dict. This is a deliberate, flagged
placeholder -- it does NOT survive a server restart and does NOT work
across multiple server processes/workers. Fine for a single-process
hackathon demo; NOT fine for anything beyond that.

TODO (coordinate with Osin): swap _SESSIONS for real persistence once
db/schema.sql exists. The table shape below is designed to map
directly onto a SQL table with zero interface changes needed upstream
-- only get_session/create_session/update_session/delete_session
bodies would change from dict ops to SQL queries. Suggested schema
(same one from the task breakdown doc):

    CREATE TABLE pending_disambiguation (
        conversation_id TEXT PRIMARY KEY,
        household_id TEXT NOT NULL,
        intake_output TEXT NOT NULL,       -- JSON blob
        remaining_vague_signs TEXT NOT NULL, -- JSON list
        resolved_signs TEXT NOT NULL,      -- JSON blob, grows each turn
        attempts_so_far TEXT NOT NULL,     -- JSON dict, sign_key -> int
        language TEXT NOT NULL DEFAULT 'en',
        created_at TEXT NOT NULL
    );
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DisambiguationSession:
    conversation_id: str
    household_id: str
    intake_output: dict            # full original IntakeResult.to_dict()
    remaining_vague_signs: list    # sign_keys still unresolved
    resolved_signs: dict           # field_name -> value, grows each turn
    attempts_so_far: dict = field(default_factory=dict)  # sign_key -> int
    language: str = "en"
    created_at: float = field(default_factory=time.time)


# In-memory store -- see module docstring for the real-persistence TODO.
_SESSIONS: dict[str, DisambiguationSession] = {}

# Simple TTL so abandoned conversations (mother never answers the
# follow-up) don't accumulate forever in memory during a long demo/test
# session. Not a replacement for real expiry logic in a production DB.
_SESSION_TTL_SECONDS = 30 * 60  # 30 minutes


def create_session(
    household_id: str,
    intake_output: dict,
    remaining_vague_signs: list,
    resolved_signs: dict,
    language: str = "en",
) -> DisambiguationSession:
    conversation_id = str(uuid.uuid4())
    session = DisambiguationSession(
        conversation_id=conversation_id,
        household_id=household_id,
        intake_output=intake_output,
        remaining_vague_signs=list(remaining_vague_signs),
        resolved_signs=dict(resolved_signs),
        language=language,
    )
    _SESSIONS[conversation_id] = session
    return session


def get_session(conversation_id: str) -> Optional[DisambiguationSession]:
    _evict_expired()
    return _SESSIONS.get(conversation_id)


def update_session(session: DisambiguationSession) -> None:
    _SESSIONS[session.conversation_id] = session


def delete_session(conversation_id: str) -> None:
    _SESSIONS.pop(conversation_id, None)


def _evict_expired() -> None:
    now = time.time()
    expired = [
        cid for cid, s in _SESSIONS.items()
        if now - s.created_at > _SESSION_TTL_SECONDS
    ]
    for cid in expired:
        _SESSIONS.pop(cid, None)