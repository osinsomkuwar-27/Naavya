"""
db/repository.py
================
Async repository functions for the Naavya / NeoTriage database layer.

This is the **only** file that teammates need to import.  It hides all
MongoDB-specific implementation details (collection names, query operators,
serialisation) behind a clean async API.

Public API
----------
    create_or_update_session(state)  -> None
    get_session(conversation_id)     -> SessionState | None
    delete_session(conversation_id)  -> bool
    log_interaction(entry)           -> None
    get_logs(conversation_id, stage) -> list[InteractionLog]

See each function's docstring for full usage examples.

PRIVACY REMINDER
----------------
Never pass PII into input_data / output_data.  See db/models.py for the
full list of prohibited field types.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from db.connection import interaction_logs_collection, sessions_collection
from db.models import InteractionLog, SessionState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _handle_mongo_error(operation: str, exc: PyMongoError) -> None:
    """
    Log a MongoDB error and re-raise it as a RuntimeError with a clear message.

    Parameters
    ----------
    operation:
        Human-readable description of the failing operation.
    exc:
        The original PyMongoError.
    """
    logger.error("[db/repository] %s failed: %s", operation, exc, exc_info=True)
    raise RuntimeError(
        f"Database error during '{operation}'. "
        f"Check your MongoDB connection and try again. Details: {exc}"
    ) from exc


# ---------------------------------------------------------------------------
# Session functions
# ---------------------------------------------------------------------------

async def create_or_update_session(state: SessionState) -> None:
    """
    Upsert a ``SessionState`` document identified by ``conversation_id``.

    Creates the document on first call; overwrites all mutable fields on
    subsequent calls.  ``created_at`` is preserved on updates via a
    ``$setOnInsert`` guard.

    Parameters
    ----------
    state:
        The fully-populated ``SessionState`` to persist.

    Raises
    ------
    RuntimeError
        Wraps any ``PyMongoError`` with a human-readable message.

    Example
    -------
    ::

        from db.repository import create_or_update_session
        from db.models import SessionState

        await create_or_update_session(
            SessionState(
                conversation_id=conv_id,
                status="intake",
                extracted_signs={"fast_breathing": True},
            )
        )
    """
    now = _utcnow()
    doc = state.model_dump()

    try:
        await sessions_collection.update_one(
            filter={"conversation_id": state.conversation_id},
            update={
                "$set": {
                    **{k: v for k, v in doc.items() if k != "created_at"},
                    "updated_at": now,
                },
                # Only write created_at when the document is first inserted.
                "$setOnInsert": {"created_at": doc.get("created_at", now)},
            },
            upsert=True,
        )
    except PyMongoError as exc:
        _handle_mongo_error(
            f"create_or_update_session(conversation_id={state.conversation_id})",
            exc,
        )


async def get_session(conversation_id: str) -> Optional[SessionState]:
    """
    Retrieve the ``SessionState`` for a given conversation.

    Parameters
    ----------
    conversation_id:
        The opaque UUID that identifies the session.

    Returns
    -------
    SessionState | None
        The session document, or ``None`` if no session exists.

    Raises
    ------
    RuntimeError
        Wraps any ``PyMongoError`` with a human-readable message.

    Example
    -------
    ::

        from db.repository import get_session

        session = await get_session(conv_id)
        if session is None:
            # First message; start intake
            ...
        else:
            current_status = session.status
    """
    try:
        doc: Optional[dict[str, Any]] = await sessions_collection.find_one(
            {"conversation_id": conversation_id},
            projection={"_id": 0},
        )
    except PyMongoError as exc:
        _handle_mongo_error(
            f"get_session(conversation_id={conversation_id})", exc
        )
        return None  # unreachable; satisfies type-checker

    if doc is None:
        return None

    return SessionState(**doc)


async def delete_session(conversation_id: str) -> bool:
    """
    Delete the ``SessionState`` for a given conversation.

    Intended for use after a session expires or is explicitly closed.

    Parameters
    ----------
    conversation_id:
        The opaque UUID that identifies the session.

    Returns
    -------
    bool
        ``True`` if a document was deleted, ``False`` if none was found.

    Raises
    ------
    RuntimeError
        Wraps any ``PyMongoError`` with a human-readable message.

    Example
    -------
    ::

        from db.repository import delete_session

        deleted = await delete_session(conv_id)
        if deleted:
            logger.info("Session %s cleaned up.", conv_id)
    """
    try:
        result = await sessions_collection.delete_one(
            {"conversation_id": conversation_id}
        )
        return result.deleted_count > 0
    except PyMongoError as exc:
        _handle_mongo_error(
            f"delete_session(conversation_id={conversation_id})", exc
        )
        return False  # unreachable; satisfies type-checker


# ---------------------------------------------------------------------------
# Interaction log functions
# ---------------------------------------------------------------------------

async def log_interaction(entry: InteractionLog) -> None:
    """
    Append an ``InteractionLog`` document to the audit collection.

    This is an insert-only operation — log entries are never modified.

    Parameters
    ----------
    entry:
        The fully-populated ``InteractionLog`` to store.

    Raises
    ------
    RuntimeError
        Wraps any ``PyMongoError`` with a human-readable message.

    Example
    -------
    ::

        from db.repository import log_interaction
        from db.models import InteractionLog

        await log_interaction(
            InteractionLog(
                conversation_id=conv_id,
                stage="intake",
                input_data=transcript_text,       # PII-free
                output_data={"fast_breathing": True},
            )
        )
    """
    try:
        await interaction_logs_collection.insert_one(entry.model_dump())
    except PyMongoError as exc:
        _handle_mongo_error(
            f"log_interaction(conversation_id={entry.conversation_id}, "
            f"stage={entry.stage})",
            exc,
        )


async def get_logs(
    conversation_id: str,
    stage: Optional[str] = None,
    limit: int = 100,
) -> list[InteractionLog]:
    """
    Retrieve interaction log entries for a conversation.

    Parameters
    ----------
    conversation_id:
        Filter logs to this conversation.
    stage:
        Optional stage filter (e.g. ``"intake"``, ``"risk_combination"``).
        When ``None``, all stages are returned.
    limit:
        Maximum number of documents to return (default: 100).
        Ordered by ``timestamp`` ascending.

    Returns
    -------
    list[InteractionLog]
        A (possibly empty) list of log entries, oldest first.

    Raises
    ------
    RuntimeError
        Wraps any ``PyMongoError`` with a human-readable message.

    Example
    -------
    ::

        from db.repository import get_logs

        # All logs for a session
        logs = await get_logs(conv_id)

        # Only risk_combination stage logs
        risk_logs = await get_logs(conv_id, stage="risk_combination")
    """
    query: dict[str, Any] = {"conversation_id": conversation_id}
    if stage is not None:
        query["stage"] = stage

    try:
        cursor = (
            interaction_logs_collection
            .find(query, projection={"_id": 0})
            .sort("timestamp", 1)
            .limit(limit)
        )
        docs: list[dict[str, Any]] = await cursor.to_list(length=limit)
    except PyMongoError as exc:
        _handle_mongo_error(
            f"get_logs(conversation_id={conversation_id}, stage={stage})", exc
        )
        return []  # unreachable; satisfies type-checker

    return [InteractionLog(**doc) for doc in docs]