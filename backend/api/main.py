"""
backend/api/main.py
Owner: Soham (+ Osin wiring for frontend connection)

FastAPI app entrypoint. Wires together:
- integrations/whatsapp/webhook.py  -> WhatsApp Cloud API messages
- backend/api/routes/assess.py      -> shared /assess endpoint used by
                                        both WhatsApp and the web mic
                                        fallback (Osin's frontend calls
                                        this directly)

Run locally:
    uvicorn backend.api.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from integrations.whatsapp.webhook import router as whatsapp_router
from backend.api.routes.assess import router as assess_router

app = FastAPI(
    title="NeoTriage API",
    description=(
        "Voice-first newborn danger-sign triage. Accepts input from "
        "WhatsApp voice notes or the web mic fallback, runs it through "
        "the intake -> disambiguation -> risk-combination -> "
        "escalation pipeline, and returns a spoken/text response."
    ),
    version="0.1.0", 
)

# Osin's frontend runs on a different origin during local dev -- keep
# this permissive for the hackathon, tighten before any public deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whatsapp_router, tags=["whatsapp"])
app.include_router(assess_router, tags=["assess"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "neotriage-api"}