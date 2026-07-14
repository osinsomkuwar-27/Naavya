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
      -> [Osin] log_write() to db

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
"""

from enum import Enum
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from asr.transcribe import transcribe, TranscriptionError
from agents.intake.intake_agent import extract_signs, IntakeResult

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
    detail: Optional[str] = None


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

    household_id links the assessment to a specific mother/ASHA pairing
    for logging and the ASHA alert -- Osin's db/schema.sql should key
    logs on this.
    """
    if audio is None and not text:
        raise HTTPException(
            status_code=400, detail="Provide either an audio file or text."
        )

    # 1. Get transcript
    if audio is not None:
        audio_bytes = await audio.read()
        try:
            result = transcribe(audio_bytes, language_hint=language_hint)
            transcript_text = result.text
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

    # 2. Intake: extract candidate signs
    intake_result: IntakeResult = extract_signs(transcript_text)
    intake_dict = intake_result.to_dict()

    # 3. Disambiguation (Shreeja) -- only runs if vague_signs is non-empty
    resolved_signs = dict(intake_result.clear_signs)
    if intake_result.vague_signs:
        try:
            from agents.disambiguation.disambiguation_agent import DisambiguationAgent

            # NOTE: for the PoC's synchronous HTTP flow, disambiguation
            # follow-up questions can't be asked mid-request over plain
            # REST -- this needs either a multi-turn conversation ID
            # (mother calls back / sends a follow-up voice note) or a
            # WebSocket for the live phone-call demo. Flagging this as
            # an open integration point for Soham + Shreeja to align on
            # before Round 1 -- NOT silently resolved here.
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

    # 4. Risk combination (Kshitij) -- classify against IMNCI rule table
    try:
        from agents.risk_combination.risk_agent import RiskCombinationAgent

        risk_agent = RiskCombinationAgent()
        risk_output = risk_agent.classify(resolved_signs, source=intake_result.source)
    except ImportError:
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

    # 5. Escalation (Shreeja) -- build spoken reply + ASHA alert if needed
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