"""
integrations/whatsapp/webhook.py
Owner: Soham

Receives incoming WhatsApp messages via the WhatsApp Business Cloud API,
pulls out voice-note audio (or plain text), and hands it off to the
shared pipeline: transcribe -> intake -> (Shreeja's disambiguation ->
Kshitij's risk agent) -> (Shreeja's TTS/escalation) -> reply.

This module only knows about WhatsApp transport concerns (verification,
webhook payload shape, media download, sending replies). All pipeline
logic lives in backend/api/routes/assess.py so the same core flow can
be reused by the web mic fallback.
"""

import os
import httpx
from fastapi import APIRouter, Request, Response, HTTPException

from asr.transcribe import transcribe, TranscriptionError
from agents.intake.intake_agent import extract_signs

router = APIRouter()

WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
GRAPH_API_BASE = "https://graph.facebook.com/v20.0"


@router.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    """
    Meta calls this once when you register the webhook URL in the
    WhatsApp Business dashboard, to prove you own the endpoint.
    See sandbox_config.md for the exact setup steps.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/whatsapp")
async def receive_message(request: Request):
    """
    Handles incoming message events. WhatsApp sends both text and voice
    notes through this same endpoint -- payload shape tells us which.
    """
    payload = await request.json()

    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]["value"]
        messages = change.get("messages")
        if not messages:
            # Could be a status update (delivered/read) rather than a
            # new message -- nothing to do.
            return {"status": "ignored"}

        message = messages[0]
        sender_id = message["from"]
        msg_type = message["type"]

    except (KeyError, IndexError) as e:
        raise HTTPException(status_code=400, detail=f"Malformed payload: {e}")

    if msg_type == "audio":
        media_id = message["audio"]["id"]
        audio_bytes = await _download_media(media_id)

        try:
            transcription = transcribe(audio_bytes)
        except TranscriptionError as e:
            await _send_text_reply(
                sender_id,
                "Sorry, I couldn't hear that clearly. Could you send the "
                "voice message again, speaking slowly?",
            )
            return {"status": "transcription_failed", "detail": str(e)}

        transcript_text = transcription.text

    elif msg_type == "text":
        transcript_text = message["text"]["body"]

    else:
        await _send_text_reply(
            sender_id,
            "Please send a voice message or type what's happening with "
            "the baby.",
        )
        return {"status": "unsupported_type", "type": msg_type}

    intake_result = extract_signs(transcript_text)

    # NOTE: hand-off point. In the full pipeline, intake_result.to_dict()
    # goes to Shreeja's DisambiguationAgent.resolve_all() for any
    # vague_signs, then the merged structured signs go to Kshitij's
    # Risk Combination Agent. That orchestration lives in
    # backend/api/routes/assess.py's process_pipeline() -- call it from
    # here once that function is wired up, so WhatsApp and the web PoC
    # share one code path instead of duplicating pipeline logic.
    #
    # from backend.api.routes.assess import process_pipeline
    # pipeline_result = await process_pipeline(intake_result, sender_id=sender_id)

    return {
        "status": "received",
        "sender": sender_id,
        "transcript": transcript_text,
        "intake": intake_result.to_dict(),
    }


async def _download_media(media_id: str) -> bytes:
    """WhatsApp media downloads are two-step: get a temporary URL for
    the media_id, then fetch the actual bytes from that URL."""
    headers = {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"}

    async with httpx.AsyncClient() as client:
        meta_resp = await client.get(
            f"{GRAPH_API_BASE}/{media_id}", headers=headers
        )
        meta_resp.raise_for_status()
        media_url = meta_resp.json()["url"]

        media_resp = await client.get(media_url, headers=headers)
        media_resp.raise_for_status()
        return media_resp.content


async def _send_text_reply(to: str, body: str) -> None:
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_API_BASE}/{WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()