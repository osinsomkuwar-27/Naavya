"""
backend/api/routes/assess.py
Owner: Soham (+ Osin wiring)

The single shared entrypoint for the triage pipeline. Both the WhatsApp
webhook and Osin's web mic fallback ultimately call process_pipeline()
here, so there is exactly one place that orchestrates:

    transcribe (if audio)
      -> intake_agent.extract_signs()
      -> [Shreeja] disambiguation_agent.resolve_all()  (for vague_signs)
      -> [Kshitij] risk_agent.classify()
      -> [Shreeja] escalation_agent.build_reply() + ASHA alert
      -> MongoDB session + interaction logs  (via db/ layer)

This keeps WhatsApp and web as two thin "input adapters" over one
pipeline, instead of duplicating orchestration logic in two places.

STATUS NOTE: Shreeja's disambiguation/escalation agents and Kshitij's
risk_combination agent are being built in parallel on their own
branches (see agents/disambiguation/, agents/risk_combination/,
agents/escalation/). This file imports them defensively -- if a
teammate's module isn't merged into your local branch yet, /assess
still runs the intake step and returns a clear "pipeline incomplete"
response instead of crashing, so this endpoint stays testable in
isolation. Once everyone's branches are merged, remove the try/except
guards and import directly.

DB INTEGRATION NOTE: MongoDB calls are wrapped in try/except so that a
transient Atlas outage never brings down the API response. All db errors
are logged at ERROR level and the endpoint continues normally.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from asr.transcribe import TranscriptionError, transcribe
from agents.intake.intake_agent import IntakeResult, extract_signs

# ---------------------------------------------------------------------------
# DB layer — imported defensively so a missing dep doesn't crash startup.
# If the import fails the endpoint still works; db calls are silently skipped.
# ---------------------------------------------------------------------------
try:
    from db import (
        InteractionLog,
        SessionState,
        create_or_update_session,
        get_session,
        log_interaction,
    )
    _DB_AVAILABLE = True
    logging.getLogger(__name__).info("MongoDB db/ layer loaded successfully.")
except Exception as _db_import_err:  # noqa: BLE001
    _DB_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "db/ layer could not be imported — MongoDB logging disabled. "
        "Error: %s",
        _db_import_err,
    )

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class InputSource(str, Enum):
    WHATSAPP = "whatsapp"
    WEB_MIC = "web_mic"
    WEB_TEXT = "web_text"  # typed fallback, e.g. for judges during demo


class AssessResponse(BaseModel):
    status: str
    transcript: Optional[str] = None
    intake: Optional[dict] = None
    pipeline_stage_reached: str
    reply_text: Optional[str] = None
    urgency: Optional[str] = None
    detail: Optional[str] = None


# ---------------------------------------------------------------------------
# DB helper utilities
# ---------------------------------------------------------------------------

async def _db_log(
    conversation_id: str,
    stage: str,
    input_data: Any,
    output_data: Any,
) -> None:
    """
    Append an InteractionLog entry for *stage*.

    Failures are caught and logged; they never propagate to the caller.
    """
    if not _DB_AVAILABLE:
        return
    try:
        await log_interaction(
            InteractionLog(
                conversation_id=conversation_id,
                stage=stage,
                input_data=input_data,
                output_data=output_data,
            )
        )
        logger.info("Interaction logged  conversation_id=%s  stage=%s", conversation_id, stage)
    except Exception:  # noqa: BLE001
        logger.error(
            "Failed to log interaction  conversation_id=%s  stage=%s",
            conversation_id,
            stage,
            exc_info=True,
        )


async def _db_upsert_session(state: "SessionState") -> None:
    """
    Upsert a SessionState document.

    Failures are caught and logged; they never propagate to the caller.
    """
    if not _DB_AVAILABLE:
        return
    try:
        await create_or_update_session(state)
        logger.info(
            "Session updated  conversation_id=%s  status=%s",
            state.conversation_id,
            state.status,
        )
    except Exception:  # noqa: BLE001
        logger.error(
            "Failed to upsert session  conversation_id=%s",
            state.conversation_id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/assess", response_model=AssessResponse)
async def assess(
    source: InputSource = Form(...),
    household_id: str = Form(...),
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    language_hint: Optional[str] = Form(None),
):
    """
    Single entrypoint for both input paths:
      - source=web_mic / whatsapp with an `audio` file upload
      - source=web_text with a `text` field (typed fallback / demo safety net)

    household_id is used as the conversation_id throughout the db layer,
    linking all pipeline stage logs to this session.
    """
    if audio is None and not text:
        raise HTTPException(
            status_code=400, detail="Provide either an audio file or text."
        )

    # Use household_id as the stable conversation identifier for this session.
    conv_id: str = household_id

    # ------------------------------------------------------------------
    # 1. Transcription
    # ------------------------------------------------------------------
    if audio is not None:
        audio_bytes = await audio.read()
        try:
            result = transcribe(audio_bytes, language_hint=language_hint)
            transcript_text = result.text
        except TranscriptionError as e:
            await _db_log(
                conversation_id=conv_id,
                stage="asr",
                input_data={"source": source, "language_hint": language_hint},
                output_data={"error": str(e)},
            )
            return AssessResponse(
                status="error",
                pipeline_stage_reached="transcription",
                detail=str(e),
                reply_text=(
                    "Sorry, I couldn't hear that clearly. Please try "
                    "speaking again, slowly and close to the phone."
                ),
            )

        await _db_log(
            conversation_id=conv_id,
            stage="asr",
            input_data={"source": source, "language_hint": language_hint},
            output_data={"transcript": transcript_text},
        )
    else:
        transcript_text = text

    # ------------------------------------------------------------------
    # 2. Intake — extract candidate signs
    # ------------------------------------------------------------------
    intake_result: IntakeResult = extract_signs(transcript_text)
    intake_dict = intake_result.to_dict()

    await _db_log(
        conversation_id=conv_id,
        stage="intake",
        input_data={"transcript": transcript_text},
        output_data=intake_dict,
    )

    # Initialise / refresh the session after intake so later agents can
    # read partial state even if the pipeline exits early.
    await _db_upsert_session(
        SessionState(
            conversation_id=conv_id,
            status="intake",
            extracted_signs=dict(intake_result.clear_signs),
        )
    )

    # ------------------------------------------------------------------
    # 3. Disambiguation (Shreeja) — only runs if vague_signs is non-empty
    # ------------------------------------------------------------------
    resolved_signs = dict(intake_result.clear_signs)
    if intake_result.vague_signs:
        try:
            from agents.disambiguation.disambiguation_agent import DisambiguationAgent  # noqa: F401

            # NOTE: for the PoC's synchronous HTTP flow, disambiguation
            # follow-up questions can't be asked mid-request over plain
            # REST -- this needs either a multi-turn conversation ID
            # (mother calls back / sends a follow-up voice note) or a
            # WebSocket for the live phone-call demo. Flagging this as
            # an open integration point for Soham + Shreeja to align on
            # before Round 1 -- NOT silently resolved here.
            await _db_log(
                conversation_id=conv_id,
                stage="disambiguation",
                input_data={"vague_signs": intake_result.vague_signs},
                output_data={"status": "pending_multi_turn"},
            )
            await _db_upsert_session(
                SessionState(
                    conversation_id=conv_id,
                    status="disambiguating",
                    extracted_signs=resolved_signs,
                    pending_question=(
                        f"Follow-up needed for: {intake_result.vague_signs}"
                    ),
                )
            )
            return AssessResponse(
                status="needs_disambiguation",
                transcript=transcript_text,
                intake=intake_dict,
                pipeline_stage_reached="disambiguation_pending",
                detail=(
                    f"Vague signs need follow-up questions: "
                    f"{intake_result.vague_signs}. Multi-turn wiring "
                    f"not yet connected in this endpoint."
                ),
            )
        except ImportError:
            await _db_log(
                conversation_id=conv_id,
                stage="disambiguation",
                input_data={"vague_signs": intake_result.vague_signs},
                output_data={"status": "agent_unavailable"},
            )
            return AssessResponse(
                status="partial",
                transcript=transcript_text,
                intake=intake_dict,
                pipeline_stage_reached="intake_only",
                detail=(
                    "Disambiguation agent not available in this branch "
                    "yet -- returning intake output only."
                ),
            )

    # ------------------------------------------------------------------
    # 4. Risk combination (Kshitij) — classify against IMNCI rule table
    # ------------------------------------------------------------------
    try:
        from agents.risk_combination.risk_agent import RiskCombinationAgent

        risk_agent = RiskCombinationAgent()
        risk_output = risk_agent.classify(resolved_signs, source=intake_result.source)

        await _db_log(
            conversation_id=conv_id,
            stage="risk_combination",
            input_data={"resolved_signs": resolved_signs},
            output_data=risk_output if isinstance(risk_output, dict) else {"result": str(risk_output)},
        )

        # Derive risk_level from the agent output (string or dict).
        risk_level: Optional[str] = (
            risk_output.get("urgency") or risk_output.get("risk_level")
            if isinstance(risk_output, dict)
            else str(risk_output)
        )

        await _db_upsert_session(
            SessionState(
                conversation_id=conv_id,
                status="classified",
                extracted_signs=resolved_signs,
                risk_level=risk_level,
            )
        )

    except ImportError:
        await _db_log(
            conversation_id=conv_id,
            stage="risk_combination",
            input_data={"resolved_signs": resolved_signs},
            output_data={"status": "agent_unavailable"},
        )
        return AssessResponse(
            status="partial",
            transcript=transcript_text,
            intake=intake_dict,
            pipeline_stage_reached="intake_complete_risk_agent_unavailable",
            detail=(
                "Risk Combination Agent not available in this branch "
                "yet -- intake pipeline is working correctly."
            ),
        )

    # ------------------------------------------------------------------
    # 5. Escalation (Shreeja) — build spoken reply + ASHA alert if needed
    # ------------------------------------------------------------------
    try:
        from agents.escalation.escalation_agent import EscalationAgent

        escalation_agent = EscalationAgent()
        reply_text = escalation_agent.build_reply(risk_output)

        await _db_log(
            conversation_id=conv_id,
            stage="escalation",
            input_data=risk_output if isinstance(risk_output, dict) else {"result": str(risk_output)},
            output_data={"reply_text": reply_text},
        )

    except ImportError:
        reply_text = None
        await _db_log(
            conversation_id=conv_id,
            stage="escalation",
            input_data=risk_output if isinstance(risk_output, dict) else {"result": str(risk_output)},
            output_data={"status": "agent_unavailable"},
        )

    # Mark session as fully processed.
    await _db_upsert_session(
        SessionState(
            conversation_id=conv_id,
            status="classified",
            extracted_signs=resolved_signs,
            risk_level=risk_level,
        )
    )

    return AssessResponse(
        status="complete",
        transcript=transcript_text,
        intake=intake_dict,
        pipeline_stage_reached="escalation",
        reply_text=reply_text,
        urgency=risk_output.get("urgency") if isinstance(risk_output, dict) else None,
    )