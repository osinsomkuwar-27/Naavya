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
from enum import Enum
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
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

MAX_DISAMBIGUATION_ROUNDS = 3

# ---------------------------------------------------------------------------
# FastAPI router — this is what main.py imports
# ---------------------------------------------------------------------------
router = APIRouter()


# ---------------------------------------------------------------------------
# Input source enum
# ---------------------------------------------------------------------------

class InputSource(str, Enum):
    whatsapp = "whatsapp"
    web_mic = "web_mic"
    web_text = "web_text"


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class AssessRequest(BaseModel):
    """Body for POST /assess."""

    transcript: str
    conversation_id: Optional[str] = None  # client may supply for multi-turn
    language: Optional[str] = "en"
    source: Optional[str] = "web_text"

    model_config = {
        "json_schema_extra": {
            "example": {
                "transcript": "My baby is 10 days old and has fast breathing.",
                "language": "en",
                "source": "web_text",
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
    source: Optional[str] = None


# ---------------------------------------------------------------------------
# Urgency → response risk_level mapping
# ---------------------------------------------------------------------------

_URGENCY_TO_RISK_LEVEL: dict[str, str] = {
    "refer_now": "refer_now",
    "monitor_recheck": "contact_asha",
    "reassure": "reassure",
}

# Structured next_steps by urgency — populates the response field alongside
# the EscalationAgent's narrative reply_text.
_NEXT_STEPS_BY_URGENCY: dict[str, list[str]] = {
    "refer_now": [
        "Go to the nearest hospital or facility right now.",
        "Keep your baby warm on the way.",
        "Call ahead if you can so they are ready.",
        "Bring any medicines your baby is already taking.",
    ],
    "monitor_recheck": [
        "Call your ASHA worker now.",
        "Keep your baby warm and continue feeding little and often.",
        "Note any new symptoms so you can share them.",
        "If things get worse quickly, go to the nearest facility.",
    ],
    "reassure": [
        "Keep your baby warm and comfortable.",
        "Continue regular feeding.",
        "Check temperature and behaviour every few hours.",
        "Start a new assessment if anything changes.",
    ],
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
# Pipeline agent imports — lazy for consistency with _get_db / _get_intake
# ---------------------------------------------------------------------------

def _get_disambiguation_agent():
    """Import DisambiguationAgent."""
    from agents.disambiguation.disambiguation_agent import DisambiguationAgent
    return DisambiguationAgent


def _get_escalation_agent():
    """Import EscalationAgent."""
    from agents.escalation.escalation_agent import EscalationAgent
    return EscalationAgent


def _get_risk_agent():
    """Import RiskCombinationAgent."""
    from agents.risk_combination.risk_agent import RiskCombinationAgent
    return RiskCombinationAgent


def _get_transcriber():
    """Import transcribe + TranscriptionError from the ASR module."""
    from asr.transcribe import transcribe, TranscriptionError
    return transcribe, TranscriptionError


def _get_session_store():
    """Import session store types and functions for multi-turn disambiguation."""
    from backend.api.session.store import (
        DisambiguationSession, get_session, update_session, delete_session,
    )
    return DisambiguationSession, get_session, update_session, delete_session


# ---------------------------------------------------------------------------
# Shared pipeline implementation
# ---------------------------------------------------------------------------

async def _run_pipeline(
    transcript: str,
    conv_id: str,
    language: str,
    source: str,
) -> AssessResponse:
    """
    Full triage pipeline shared by both the text and voice endpoints.

    Stages logged to MongoDB:
      1. intake           – LLM extraction of danger signs
      2. disambiguation   – multi-turn clarifying questions for vague signs
      3. risk_combination – IMNCI rule matching
      4. escalation       – human-readable recommendation generation
    """
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
    # Load session store (non-fatal — if unavailable, disambiguation
    # falls back to single-turn mode with a static question)
    # ------------------------------------------------------------------
    session_store_available = True
    try:
        DisambiguationSession, sess_get, sess_update, sess_delete = _get_session_store()
    except Exception as exc:
        logger.warning("[%s] Session store unavailable: %s", conv_id, exc)
        session_store_available = False

    # ------------------------------------------------------------------
    # Check for an existing disambiguation session (multi-turn follow-up)
    # ------------------------------------------------------------------
    existing_session = None
    if session_store_available:
        existing_session = sess_get(conv_id)
        logger.info("[%s] session lookup → found=%s remaining=%s", conv_id,
                existing_session is not None,
                existing_session.remaining_vague_signs if existing_session else None)

    # If a session exists, try to load the disambiguation agent for it.
    # On failure, delete the stale session and fall through to fresh intake.
    disambig_agent = None
    if existing_session is not None:
        logger.info("[%s] Resuming disambiguation session", conv_id)
        try:
            DisambiguationAgentCls = _get_disambiguation_agent()
            disambig_agent = DisambiguationAgentCls(language=existing_session.language)
        except Exception as exc:
            logger.error("[%s] Failed to load DisambiguationAgent for resume: %s", conv_id, exc)
            sess_delete(conv_id)
            existing_session = None

    # ------------------------------------------------------------------
    # PATH A: Resume an active disambiguation session
    # ------------------------------------------------------------------
    if existing_session is not None and existing_session.remaining_vague_signs:
        current_sign = existing_session.remaining_vague_signs[0]
        attempts = existing_session.attempts_so_far.get(current_sign, 0)

        result = disambig_agent.resume_disambiguation(
            sign_key=current_sign,
            answer_text=transcript,
            already_resolved=dict(existing_session.resolved_signs),
            already_unresolved=[],
            attempts_so_far=attempts,
        )

        if result["status"] == "resolved":
            existing_session.resolved_signs = result["resolved_signs"]
            existing_session.remaining_vague_signs.pop(0)
        elif result["status"] == "unresolved":
            existing_session.audit_flags = existing_session.intake_output.get("audit_flags", []) + [
                f"Sign '{current_sign}' could not be resolved after {MAX_DISAMBIGUATION_ROUNDS} attempts."
            ]
            existing_session.resolved_signs[current_sign] = "unresolved"
            existing_session.remaining_vague_signs.pop(0)
        elif result["status"] == "ask_again":
            # Same sign needs another attempt
            existing_session.attempts_so_far[current_sign] = attempts + 1
            sess_update(existing_session)

            pending_q = result["question"]

            if db_available:
                try:
                    await create_or_update_session(
                        SessionState(
                            conversation_id=conv_id,
                            status="disambiguating",
                            extracted_signs=existing_session.resolved_signs,
                            pending_question=pending_q,
                        )
                    )
                    await log_interaction(
                        InteractionLog(
                            conversation_id=conv_id,
                            stage="disambiguation",
                            input_data={"answer": transcript, "sign_key": current_sign},
                            output_data={"status": "ask_again", "question": pending_q},
                        )
                    )
                except Exception as exc:
                    logger.error("[%s] DB write FAILED at disambiguation stage: %s", conv_id, exc, exc_info=True)

            return AssessResponse(
                conversation_id=conv_id,
                status="disambiguating",
                pending_question=pending_q,
                clear_signs=existing_session.intake_output.get("clear_signs", {}),
                vague_signs=existing_session.remaining_vague_signs,
                source=source,
            )

        # Check if more vague signs remain after processing the current one
        if existing_session.remaining_vague_signs:
            next_sign = existing_session.remaining_vague_signs[0]
            pending_q = disambig_agent.get_question(next_sign)
            sess_update(existing_session)

            if db_available:
                try:
                    await create_or_update_session(
                        SessionState(
                            conversation_id=conv_id,
                            status="disambiguating",
                            extracted_signs={
                                **existing_session.intake_output.get("clear_signs", {}),
                                **existing_session.resolved_signs,
                            },
                            pending_question=pending_q,
                        )
                    )
                    await log_interaction(
                        InteractionLog(
                            conversation_id=conv_id,
                            stage="disambiguation",
                            input_data={"answer": transcript, "sign_key": current_sign},
                            output_data={"status": "next_sign", "next_sign": next_sign, "question": pending_q},
                        )
                    )
                except Exception as exc:
                    logger.error("[%s] DB write FAILED at disambiguation stage: %s", conv_id, exc, exc_info=True)

            return AssessResponse(
                conversation_id=conv_id,
                status="disambiguating",
                pending_question=pending_q,
                clear_signs={
                    **existing_session.intake_output.get("clear_signs", {}),
                    **existing_session.resolved_signs,
                },
                vague_signs=existing_session.remaining_vague_signs,
                source=source,
            )

        # All vague signs processed — merge and continue to risk + escalation
        clear_signs = {
            **existing_session.intake_output.get("clear_signs", {}),
            **existing_session.resolved_signs,
        }
        vague_signs: list[str] = []
        audit_flags: list[str] = existing_session.intake_output.get("audit_flags", [])
        intake_source = existing_session.intake_output.get("source", "parent_reported_voice")
        sess_delete(conv_id)

        logger.info("[%s] Disambiguation complete — merged signs: %s", conv_id, clear_signs)

        if db_available:
            try:
                await log_interaction(
                    InteractionLog(
                        conversation_id=conv_id,
                        stage="disambiguation",
                        input_data={"answer": transcript, "sign_key": current_sign},
                        output_data={"status": "all_resolved", "resolved_signs": existing_session.resolved_signs},
                    )
                )
            except Exception as exc:
                logger.error("[%s] DB write FAILED at disambiguation stage: %s", conv_id, exc, exc_info=True)

    elif existing_session is not None:
        # Edge case: session exists but remaining_vague_signs is already empty
        clear_signs = {
            **existing_session.intake_output.get("clear_signs", {}),
            **existing_session.resolved_signs,
        }
        vague_signs = []
        audit_flags = existing_session.intake_output.get("audit_flags", [])
        intake_source = existing_session.intake_output.get("source", "parent_reported_voice")
        sess_delete(conv_id)
        logger.info("[%s] Session found with no remaining signs — merging and continuing", conv_id)

    else:
        # ------------------------------------------------------------------
        # PATH B: Fresh request — no active disambiguation session
        # ------------------------------------------------------------------

        # ------------------------------------------------------------------
        # STAGE 1: Intake — LLM sign extraction
        # ------------------------------------------------------------------
        try:
            extract_signs = _get_intake()
            intake_result = extract_signs(transcript, language=language)
            clear_signs = intake_result.clear_signs
            vague_signs = intake_result.vague_signs
            audit_flags = intake_result.audit_flags
            intake_source = intake_result.source
        except Exception as exc:
            logger.error("Intake stage failed: %s", exc, exc_info=True)
            # Fail toward caution — treat as if all signs are vague
            clear_signs = {}
            vague_signs = []
            audit_flags = [f"Intake extraction failed: {type(exc).__name__}: {exc}"]
            intake_source = "parent_reported_voice"

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
        # STAGE 2: Disambiguation — real multi-turn flow
        # If vague signs exist, start a disambiguation session and return
        # early with the first clarifying question. The next request from
        # the same conversation_id will resume via PATH A above.
        # ------------------------------------------------------------------
        if vague_signs:
            try:
                DisambiguationAgentCls = _get_disambiguation_agent()
                agent = DisambiguationAgentCls(language=language)
                first_sign = vague_signs[0]
                pending_q = agent.get_question(first_sign)
            except Exception as exc:
                logger.error("[%s] DisambiguationAgent load failed: %s", conv_id, exc, exc_info=True)
                # Fallback: generic question so the API still returns something
                pending_q = f"Could you tell me more about: {', '.join(vague_signs)}?"

            logger.info("[%s] Vague signs present — starting disambiguation", conv_id)

            # Create a disambiguation session for multi-turn follow-up
            if session_store_available:
                try:
                    intake_dict = {
                        "source": intake_source,
                        "raw_transcript": transcript,
                        "language": language,
                        "clear_signs": clear_signs,
                        "vague_signs": vague_signs,
                        "audit_flags": audit_flags,
                    }
                    session = DisambiguationSession(
                        conversation_id=conv_id,
                        household_id=conv_id,
                        intake_output=intake_dict,
                        remaining_vague_signs=list(vague_signs),
                        resolved_signs={},
                        language=language,
                    )
                    sess_update(session)
                    logger.info("[%s] Disambiguation session created", conv_id)
                except Exception as exc:
                    logger.error("[%s] Session store write failed: %s", conv_id, exc, exc_info=True)

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

            return AssessResponse(
                conversation_id=conv_id,
                status="disambiguating",
                pending_question=pending_q,
                clear_signs=clear_signs,
                vague_signs=vague_signs,
                audit_flags=audit_flags,
                source=source,
            )
    try:
        RiskCombinationAgentCls = _get_risk_agent()
        risk_agent_instance = RiskCombinationAgentCls()
        risk_output = risk_agent_instance.classify(clear_signs, source=intake_source)
    except Exception as exc:
        logger.error("[%s] Risk combination failed: %s", conv_id, exc, exc_info=True)
        # Fail toward caution — refer immediately
        risk_output = {
            "classification": "risk_agent_error",
            "urgency": "refer_now",
            "action_summary": f"Risk assessment failed ({type(exc).__name__}). Advise facility visit.",
            "follow_up_days": None,
        }

    urgency = risk_output.get("urgency", "refer_now")
    risk_level = _URGENCY_TO_RISK_LEVEL.get(urgency, "refer_now")

    logger.info("[%s] Risk combination result: %s (risk_level=%s)", conv_id, risk_output, risk_level)

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
                    input_data={"clear_signs": clear_signs, "source": intake_source},
                    output_data={"risk_output": risk_output, "risk_level": risk_level},
                )
            )
            logger.info("[%s] DB: risk_combination writes OK", conv_id)
        except Exception as exc:
            logger.error("[%s] DB write FAILED at risk_combination stage: %s", conv_id, exc, exc_info=True)

    # ------------------------------------------------------------------
    # STAGE 4: Escalation — EscalationAgent
    # ------------------------------------------------------------------
    disambiguation_output = {
        "source": intake_source,
        "signs": clear_signs,
        "safe_fallback_message": None,
        "language": language,
    }

    try:
        EscalationAgentCls = _get_escalation_agent()
        escalation_agent = EscalationAgentCls(language=language)
        escalation_result = escalation_agent.handle(
            risk_output=risk_output,
            disambiguation_output=disambiguation_output,
            household_id=conv_id,
        )
        recommendation = escalation_result.reply_text
    except Exception as exc:
        logger.error("[%s] Escalation agent failed: %s", conv_id, exc, exc_info=True)
        recommendation = "Please consult your ASHA worker or nearest health facility."

    next_steps = _NEXT_STEPS_BY_URGENCY.get(urgency, _NEXT_STEPS_BY_URGENCY["reassure"])

    logger.info("[%s] Escalation — recommendation: %s", conv_id, recommendation)

    if db_available:
        try:
            logger.info("[%s] DB: writing interaction_log (stage=escalation)...", conv_id)
            await log_interaction(
                InteractionLog(
                    conversation_id=conv_id,
                    stage="escalation",
                    input_data={"risk_output": risk_output},
                    output_data={
                        "recommendation": recommendation,
                        "next_steps": next_steps,
                        "urgency": urgency,
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
        pending_question=None,
        clear_signs=clear_signs,
        vague_signs=vague_signs,
        audit_flags=audit_flags,
        source=source,
    )


# ---------------------------------------------------------------------------
# Main text endpoint — signature preserved for API compatibility
# ---------------------------------------------------------------------------

@router.post("/assess", response_model=AssessResponse)
async def assess(req: AssessRequest) -> AssessResponse:
    """
    Full triage pipeline for a caregiver's transcript (text input).

    Stages logged to MongoDB:
      1. intake           – LLM extraction of danger signs
      2. disambiguation   – multi-turn clarifying questions
      3. risk_combination – IMNCI rule matching
      4. escalation       – human-readable recommendation generation
    """
    conv_id = req.conversation_id or str(uuid.uuid4())
    transcript = req.transcript.strip()
    language = req.language or "en"
    source = req.source or "web_text"

    return await _run_pipeline(transcript, conv_id, language, source)


# ---------------------------------------------------------------------------
# Voice/audio endpoint — restored audio input support
# ---------------------------------------------------------------------------

@router.post("/assess/voice", response_model=AssessResponse)
async def assess_voice(
    audio: UploadFile = File(..., description="Audio file (voice note or mic recording)"),
    conversation_id: Optional[str] = Form(None),
    language: Optional[str] = Form("en"),
    source: Optional[str] = Form("web_mic"),
) -> AssessResponse:
    """
    Full triage pipeline for a caregiver's voice input.

    Accepts an audio file upload (WAV, OGG, MP3, etc.), transcribes it
    via Whisper ASR, then runs the same pipeline as POST /assess.

    The ASR stage is logged to MongoDB as an additional interaction_log
    entry with stage='asr'.
    """
    conv_id = conversation_id or str(uuid.uuid4())
    lang = language or "en"
    src = source or "web_mic"

    # ------------------------------------------------------------------
    # ASR — transcribe audio to text
    # ------------------------------------------------------------------
    try:
        transcribe_fn, TranscriptionError = _get_transcriber()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"ASR module unavailable: {exc}",
        )

    try:
        audio_bytes = await audio.read()
        transcription = transcribe_fn(audio_bytes, language_hint=lang)
        transcript = transcription.text
        detected_language = transcription.language or lang
    except Exception as exc:
        logger.error("ASR transcription failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=422,
            detail=f"Could not transcribe audio. Please try again or send text instead. ({exc})",
        )

    logger.info("[%s] ASR complete — transcript: %s (lang=%s)", conv_id, transcript, detected_language)

    # Log ASR stage to DB
    db_available = True
    try:
        _, log_interaction, _, InteractionLog = _get_db()
    except Exception:
        db_available = False

    if db_available:
        try:
            await log_interaction(
                InteractionLog(
                    conversation_id=conv_id,
                    stage="asr",
                    input_data={"filename": audio.filename, "language_hint": lang, "source": src},
                    output_data={"transcript": transcript, "detected_language": detected_language},
                )
            )
        except Exception as exc:
            logger.error("[%s] DB write FAILED at ASR stage: %s", conv_id, exc, exc_info=True)

    return await _run_pipeline(transcript, conv_id, detected_language, src)