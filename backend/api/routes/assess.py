"""
backend/api/routes/assess.py
Owner: Soham (+ Osin wiring)

The single shared entrypoint for the triage pipeline. Both the WhatsApp
webhook and Osin's web mic fallback ultimately call this route, so
there is exactly one place that orchestrates:

    transcribe (if audio)
      -> intake_agent_v2.extract_signs()   [LLM-based, falls back to v1]
      -> [Shreeja] resume_disambiguation()  (multi-turn, resumable)
      -> [Kshitij] risk_agent.classify()
      -> [Shreeja] escalation_agent.build_reply() + ASHA alert
      -> [Osin] log_write() to db

MULTI-TURN DISAMBIGUATION (per team task breakdown + Shreeja's message):
A single HTTP request can't block and wait for a follow-up answer, so
when intake finds vague_signs, this endpoint:
  1. Creates a DisambiguationSession (backend/api/session/store.py),
     keyed by a new conversation_id.
  2. Returns that conversation_id + the first follow-up question to
     the caller (WhatsApp reply / web response).
  3. On the NEXT /assess call, if conversation_id is present and
     matches a pending session, the incoming text is treated as the
     ANSWER to the last question -- routed to Shreeja's
     resume_disambiguation() instead of running extract_signs() again.
  4. Repeats until all vague signs are resolved (or hit the fallback
     after max attempts), then proceeds to risk_agent as normal.

STATUS NOTE: Kshitij's risk_combination agent and Shreeja's
disambiguation/escalation agents are imported defensively -- if a
teammate's module isn't available in this branch/environment, /assess
still completes as much of the pipeline as it can rather than crashing.
"""

from enum import Enum
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from asr.transcribe import transcribe, TranscriptionError
from agents.intake.intake_agent_v2 import extract_signs, IntakeResult
from backend.api.session import store as session_store

router = APIRouter()


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
    conversation_id: Optional[str] = None
    detail: Optional[str] = None


@router.post("/assess", response_model=AssessResponse)
async def assess(
    source: InputSource = Form(...),
    household_id: str = Form(...),
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    language_hint: Optional[str] = Form(None),
    conversation_id: Optional[str] = Form(None),
):
    """
    Single entrypoint for both input paths and both conversation states:
      - New conversation: source + household_id + (audio OR text)
      - Continuing conversation: same, PLUS conversation_id from a
        previous response that had status="needs_disambiguation"
    """
    if audio is None and not text:
        raise HTTPException(
            status_code=400, detail="Provide either an audio file or text."
        )

    # 1. Get transcript (+ detected language, if this came from audio)
    detected_language = language_hint or "en"
    if audio is not None:
        audio_bytes = await audio.read()
        try:
            transcription = transcribe(audio_bytes, language_hint=language_hint)
            transcript_text = transcription.text
            detected_language = transcription.language or detected_language
        except TranscriptionError as e:
            return AssessResponse(
                status="error",
                pipeline_stage_reached="transcription",
                detail=str(e),
                reply_text=(
                    "Sorry, I couldn't hear that clearly. Please try "
                    "speaking again, slowly and close to the phone."
                ),
            )
    else:
        transcript_text = text

    # 2. Branch: is this a NEW conversation, or an ANSWER to a pending
    # disambiguation question?
    if conversation_id:
        return await _handle_disambiguation_answer(
            conversation_id, transcript_text
        )

    # --- New conversation path ---
    intake_result: IntakeResult = extract_signs(
        transcript_text, language=detected_language
    )
    intake_dict = intake_result.to_dict()
    resolved_signs = dict(intake_result.clear_signs)

    if intake_result.vague_signs:
        session = session_store.create_session(
            household_id=household_id,
            intake_output=intake_dict,
            remaining_vague_signs=intake_result.vague_signs,
            resolved_signs=resolved_signs,
            language=detected_language,
        )
        first_question = _get_next_question(session)
        return AssessResponse(
            status="needs_disambiguation",
            transcript=transcript_text,
            intake=intake_dict,
            pipeline_stage_reached="disambiguation_pending",
            conversation_id=session.conversation_id,
            reply_text=first_question,
            detail=f"Follow-up needed for: {intake_result.vague_signs}",
        )

    # No vague signs -- go straight to risk combination
    return await _run_risk_and_escalation(
        transcript_text, intake_dict, resolved_signs, detected_language
    )


async def _handle_disambiguation_answer(
    conversation_id: str, answer_text: str
) -> AssessResponse:
    """Routes an incoming request that's answering a pending follow-up
    question to Shreeja's resume_disambiguation(), instead of treating
    it as a fresh symptom description."""
    session = session_store.get_session(conversation_id)
    if session is None:
        return AssessResponse(
            status="error",
            pipeline_stage_reached="disambiguation",
            detail=(
                "conversation_id not found or expired -- start a new "
                "assessment (omit conversation_id)."
            ),
        )

    if not session.remaining_vague_signs:
        # Shouldn't normally happen, but don't crash if it does.
        session_store.delete_session(conversation_id)
        return await _run_risk_and_escalation(
            answer_text, session.intake_output, session.resolved_signs,
            session.language,
        )

    current_sign_key = session.remaining_vague_signs[0]

    try:
        from agents.disambiguation.disambiguation_agent import DisambiguationAgent

        agent = DisambiguationAgent()
        attempts = session.attempts_so_far.get(current_sign_key, 0)

        result = agent.resume_disambiguation(
            sign_key=current_sign_key,
            answer_text=answer_text,
            already_resolved=session.resolved_signs,
            already_unresolved=[],
            attempts_so_far=attempts,
        )
    except ImportError:
        session_store.delete_session(conversation_id)
        return AssessResponse(
            status="partial",
            pipeline_stage_reached="disambiguation_agent_unavailable",
            conversation_id=conversation_id,
            detail="Disambiguation agent not available in this environment.",
        )

    if result["status"] == "resolved":
        session.resolved_signs = result["resolved_signs"]
        session.remaining_vague_signs.pop(0)
        session.attempts_so_far.pop(current_sign_key, None)

        if session.remaining_vague_signs:
            session_store.update_session(session)
            next_question = _get_next_question(session)
            return AssessResponse(
                status="needs_disambiguation",
                pipeline_stage_reached="disambiguation_pending",
                conversation_id=conversation_id,
                reply_text=next_question,
                detail=f"Still need: {session.remaining_vague_signs}",
            )

        # All signs resolved -- proceed to risk combination
        session_store.delete_session(conversation_id)
        return await _run_risk_and_escalation(
            answer_text, session.intake_output, session.resolved_signs,
            session.language,
        )

    elif result["status"] == "ask_again":
        session.attempts_so_far[current_sign_key] = attempts + 1
        session_store.update_session(session)
        return AssessResponse(
            status="needs_disambiguation",
            pipeline_stage_reached="disambiguation_pending",
            conversation_id=conversation_id,
            reply_text=result["question"],
            detail=f"Re-asking for: {current_sign_key} (attempt {attempts + 1})",
        )

    else:  # "unresolved" -- hit max attempts, use safe fallback
        session.remaining_vague_signs.pop(0)
        session.attempts_so_far.pop(current_sign_key, None)

        if session.remaining_vague_signs:
            session_store.update_session(session)
            next_question = _get_next_question(session)
            return AssessResponse(
                status="needs_disambiguation",
                pipeline_stage_reached="disambiguation_pending",
                conversation_id=conversation_id,
                reply_text=next_question,
                detail=(
                    f"{current_sign_key} unresolved after max attempts, "
                    f"moving on. Still need: {session.remaining_vague_signs}"
                ),
            )

        session_store.delete_session(conversation_id)
        return await _run_risk_and_escalation(
            answer_text, session.intake_output, session.resolved_signs,
            session.language,
        )


def _get_next_question(session) -> Optional[str]:
    """Asks Shreeja's agent for the question text for the next pending
    sign. Falls back to a generic prompt if her agent isn't available
    in this environment."""
    if not session.remaining_vague_signs:
        return None
    try:
        from agents.disambiguation.disambiguation_agent import DisambiguationAgent

        agent = DisambiguationAgent()
        return agent.get_question(session.remaining_vague_signs[0])
    except ImportError:
        return (
            f"Can you tell me more about the baby's "
            f"{session.remaining_vague_signs[0]}?"
        )


async def _run_risk_and_escalation(
    transcript_text: str,
    intake_dict: dict,
    resolved_signs: dict,
    language: str,
) -> AssessResponse:
    """Shared tail end of the pipeline once all signs are resolved
    (either none were vague, or disambiguation just finished)."""
    try:
        from agents.risk_combination.risk_agent import RiskCombinationAgent

        risk_agent = RiskCombinationAgent()
        risk_output = risk_agent.classify(
            resolved_signs, source=intake_dict.get("source", "parent_reported")
        )
    except ImportError:
        return AssessResponse(
            status="partial",
            transcript=transcript_text,
            intake=intake_dict,
            pipeline_stage_reached="intake_complete_risk_agent_unavailable",
            detail=(
                "Risk Combination Agent not available in this branch "
                "yet -- intake/disambiguation pipeline is working correctly."
            ),
        )

    try:
        from agents.escalation.escalation_agent import EscalationAgent

        escalation_agent = EscalationAgent()
        reply_text = escalation_agent.build_reply(risk_output)
    except ImportError:
        reply_text = None

    return AssessResponse(
        status="complete",
        transcript=transcript_text,
        intake=intake_dict,
        pipeline_stage_reached="escalation",
        reply_text=reply_text,
        urgency=risk_output.get("urgency") if isinstance(risk_output, dict) else None,
    )