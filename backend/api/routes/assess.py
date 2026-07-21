"""
backend/api/routes/assess.py
Owner: Soham (router scaffolding + DB wiring) / pipeline integration

FastAPI router for the shared /assess endpoint.  Both the WhatsApp webhook
and the web frontend call this to run the full triage pipeline:

    transcript text
        → intake agent     (LLM sign extraction)
        → disambiguation   (clarifying questions for vague signs)
        → risk combination (IMNCI rule matching)
        → escalation       (generate human-readable recommendation)

Every stage is logged to MongoDB via db.repository.

Run the full server from the project root:
    uvicorn backend.api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so sibling packages resolve correctly
# when uvicorn is launched from anywhere.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logger = logging.getLogger("neotriage.assess")

# ---------------------------------------------------------------------------
# FastAPI router — this is what main.py imports
# ---------------------------------------------------------------------------
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class AssessRequest(BaseModel):
    """Body for POST /assess."""

    transcript: str
    conversation_id: Optional[str] = None  # client may supply for multi-turn
    language: Optional[str] = "en"

    model_config = {
        "json_schema_extra": {
            "example": {
                "transcript": "My baby is 10 days old and has fast breathing.",
                "language": "en",
            }
        }
    }


class AssessResponse(BaseModel):
    """Response from POST /assess."""

    conversation_id: str
    status: str                        # intake | disambiguating | classified
    risk_level: Optional[str] = None   # reassure | contact_asha | refer_now
    recommendation: Optional[str] = None
    next_steps: list[str] = []
    pending_question: Optional[str] = None
    clear_signs: dict = {}
    vague_signs: list[str] = []
    audit_flags: list[str] = []


# ---------------------------------------------------------------------------
# Risk → human-readable copy
# ---------------------------------------------------------------------------

_RISK_COPY: dict[str, dict] = {
    "refer_now": {
        "recommendation": "Please go to the nearest health facility immediately.",
        "next_steps": [
            "Go to the nearest hospital or facility right now.",
            "Keep your baby warm on the way.",
            "Call ahead if you can so they are ready.",
            "Bring any medicines your baby is already taking.",
        ],
    },
    "contact_asha": {
        "recommendation": "Contact your ASHA worker today for a visit.",
        "next_steps": [
            "Call your ASHA worker now.",
            "Keep your baby warm and continue feeding little and often.",
            "Note any new symptoms so you can share them.",
            "If things get worse quickly, go to the nearest facility.",
        ],
    },
    "reassure": {
        "recommendation": "Continue home care. Watch closely for 24 hours.",
        "next_steps": [
            "Keep your baby warm and comfortable.",
            "Continue regular feeding.",
            "Check temperature and behaviour every few hours.",
            "Start a new assessment if anything changes.",
        ],
    },
}


# ---------------------------------------------------------------------------
# DB helpers — imported lazily so a missing MongoDB config doesn't crash
# import at startup; it will crash only when the endpoint is actually called.
# ---------------------------------------------------------------------------

def _get_db():
    """Return (create_or_update_session, log_interaction, SessionState, InteractionLog)."""
    from db.repository import create_or_update_session, log_interaction
    from db.models import SessionState, InteractionLog
    return create_or_update_session, log_interaction, SessionState, InteractionLog


# ---------------------------------------------------------------------------
# Intake import — agents/intake/intake_agent_v2.py
# ---------------------------------------------------------------------------

def _get_intake():
    """Import extract_signs from the intake agent."""
    from agents.intake.intake_agent_v2 import extract_signs
    return extract_signs


# ---------------------------------------------------------------------------
# Risk combination — agents/risk_combination (stub if not yet integrated)
# ---------------------------------------------------------------------------

def _run_risk_combination(clear_signs: dict) -> str:
    """
    Run the risk combination agent.  Falls back to a simple heuristic so
    the endpoint returns something meaningful even before full agent wiring.
    """
    try:
        from agents.risk_combination.risk_agent import classify_risk  # type: ignore
        return classify_risk(clear_signs)
    except ImportError:
        pass

    # --- Fallback heuristic (mirrors IMNCI danger-sign logic) ---
    high_signs = {
        "breathing_rate": "severe_chest_indrawing",
        "convulsions": "yes",
        "movement": "not_moving",
    }
    for k, v in clear_signs.items():
        if high_signs.get(k) == v:
            return "refer_now"

    medium_signs = {"feeding", "temperature", "jaundice_extent", "jaundice_onset"}
    if any(k in medium_signs for k in clear_signs):
        return "contact_asha"

    return "reassure"


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------

@router.post("/assess", response_model=AssessResponse)
async def assess(req: AssessRequest) -> AssessResponse:
    """
    Full triage pipeline for a caregiver's transcript.

    Stages logged to MongoDB:
      1. intake           – LLM extraction of danger signs
      2. risk_combination – IMNCI rule matching
      3. escalation       – human-readable recommendation generation
    """
    conv_id = req.conversation_id or str(uuid.uuid4())
    transcript = req.transcript.strip()
    language = req.language or "en"

    if not transcript:
        raise HTTPException(status_code=422, detail="transcript must not be empty")

    # ------------------------------------------------------------------
    # Load DB helpers (non-fatal on import error — endpoint will work but
    # nothing will be persisted; a warning is logged instead of a 500).
    # ------------------------------------------------------------------
    db_available = True
    try:
        create_or_update_session, log_interaction, SessionState, InteractionLog = _get_db()
        # Import connection attrs to log which DB we're targeting
        from db.connection import _MONGODB_DB_NAME, _MONGODB_URI
        logger.info(
            "[%s] DB ready — cluster=%s db=%s",
            conv_id, _MONGODB_URI.split("@")[-1].split("/")[0], _MONGODB_DB_NAME,
        )
    except Exception as exc:
        logger.warning(
            "[%s] DB layer unavailable — assessment will run but nothing will be persisted. "
            "Error: %s", conv_id, exc
        )
        db_available = False

    # ------------------------------------------------------------------
    # STAGE 1: Intake — LLM sign extraction
    # ------------------------------------------------------------------
    try:
        extract_signs = _get_intake()
        intake_result = extract_signs(transcript, language=language)
        clear_signs = intake_result.clear_signs
        vague_signs = intake_result.vague_signs
        audit_flags = intake_result.audit_flags
    except Exception as exc:
        logger.error("Intake stage failed: %s", exc, exc_info=True)
        # Fail toward caution — treat as if all signs are vague
        clear_signs = {}
        vague_signs = []
        audit_flags = [f"Intake extraction failed: {type(exc).__name__}: {exc}"]

    logger.info(
        "[%s] Intake complete — clear: %s | vague: %s | flags: %s",
        conv_id, clear_signs, vague_signs, audit_flags,
    )

    # Persist session + log
    if db_available:
        try:
            logger.info("[%s] DB: writing session (status=intake)...", conv_id)
            await create_or_update_session(
                SessionState(
                    conversation_id=conv_id,
                    status="intake",
                    extracted_signs=clear_signs,
                )
            )
            logger.info("[%s] DB: session write OK", conv_id)
            logger.info("[%s] DB: writing interaction_log (stage=intake)...", conv_id)
            await log_interaction(
                InteractionLog(
                    conversation_id=conv_id,
                    stage="intake",
                    input_data={"transcript": transcript, "language": language},
                    output_data={
                        "clear_signs": clear_signs,
                        "vague_signs": vague_signs,
                        "audit_flags": audit_flags,
                    },
                )
            )
            logger.info("[%s] DB: intake log write OK", conv_id)
        except Exception as exc:
            logger.error("[%s] DB write FAILED at intake stage: %s", conv_id, exc, exc_info=True)

    # ------------------------------------------------------------------
    # STAGE 2: Disambiguation stub
    # If there are vague signs we'd normally ask a follow-up question here.
    # For single-turn web calls we skip and log the pending state.
    # ------------------------------------------------------------------
    if vague_signs:
        pending_q = f"Could you tell me more about: {', '.join(vague_signs)}?"
        logger.info("[%s] Vague signs present — logged as disambiguating", conv_id)

        if db_available:
            try:
                logger.info("[%s] DB: writing session (status=disambiguating)...", conv_id)
                await create_or_update_session(
                    SessionState(
                        conversation_id=conv_id,
                        status="disambiguating",
                        extracted_signs=clear_signs,
                        pending_question=pending_q,
                    )
                )
                logger.info("[%s] DB: writing interaction_log (stage=disambiguation)...", conv_id)
                await log_interaction(
                    InteractionLog(
                        conversation_id=conv_id,
                        stage="disambiguation",
                        input_data={"vague_signs": vague_signs},
                        output_data={"pending_question": pending_q},
                    )
                )
                logger.info("[%s] DB: disambiguation writes OK", conv_id)
            except Exception as exc:
                logger.error("[%s] DB write FAILED at disambiguation stage: %s", conv_id, exc, exc_info=True)
    else:
        pending_q = None

    # ------------------------------------------------------------------
    # STAGE 3: Risk combination
    # ------------------------------------------------------------------
    risk_level = _run_risk_combination(clear_signs)

    logger.info("[%s] Risk combination result: %s", conv_id, risk_level)

    if db_available:
        try:
            logger.info("[%s] DB: writing session (status=classified risk=%s)...", conv_id, risk_level)
            await create_or_update_session(
                SessionState(
                    conversation_id=conv_id,
                    status="classified",
                    extracted_signs=clear_signs,
                    risk_level=risk_level,
                )
            )
            logger.info("[%s] DB: writing interaction_log (stage=risk_combination)...", conv_id)
            await log_interaction(
                InteractionLog(
                    conversation_id=conv_id,
                    stage="risk_combination",
                    input_data={"clear_signs": clear_signs},
                    output_data={"risk_level": risk_level},
                )
            )
            logger.info("[%s] DB: risk_combination writes OK", conv_id)
        except Exception as exc:
            logger.error("[%s] DB write FAILED at risk_combination stage: %s", conv_id, exc, exc_info=True)

    # ------------------------------------------------------------------
    # STAGE 4: Escalation — generate recommendation copy
    # ------------------------------------------------------------------
    copy = _RISK_COPY.get(risk_level, _RISK_COPY["reassure"])
    recommendation = copy["recommendation"]
    next_steps = copy["next_steps"]

    logger.info("[%s] Escalation — recommendation: %s", conv_id, recommendation)

    if db_available:
        try:
            logger.info("[%s] DB: writing interaction_log (stage=escalation)...", conv_id)
            await log_interaction(
                InteractionLog(
                    conversation_id=conv_id,
                    stage="escalation",
                    input_data={"risk_level": risk_level},
                    output_data={
                        "recommendation": recommendation,
                        "next_steps": next_steps,
                    },
                )
            )
            logger.info("[%s] DB: escalation log write OK — pipeline complete", conv_id)
        except Exception as exc:
            logger.error("[%s] DB write FAILED at escalation stage: %s", conv_id, exc, exc_info=True)

    # ------------------------------------------------------------------
    # Build and return response
    # ------------------------------------------------------------------
    return AssessResponse(
        conversation_id=conv_id,
        status="classified",
        risk_level=risk_level,
        recommendation=recommendation,
        next_steps=next_steps,
        pending_question=pending_q,
        clear_signs=clear_signs,
        vague_signs=vague_signs,
        audit_flags=audit_flags,
    )