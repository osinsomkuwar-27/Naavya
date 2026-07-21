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


@app.on_event("startup")
async def _log_startup() -> None:
    """Log DB connection info at startup so it's obvious which cluster is in use."""
    import logging
    _log = logging.getLogger("neotriage.main")
    try:
        from db.connection import _MONGODB_URI, _MONGODB_DB_NAME, sessions_collection
        cluster = _MONGODB_URI.split("@")[-1].split("/")[0]
        _log.info(
            "[STARTUP] MongoDB ready — cluster=%s db=%s collections=sessions,interaction_logs",
            cluster, _MONGODB_DB_NAME,
        )
        # Ping the cluster to confirm network reachability
        count = await sessions_collection.count_documents({})
        _log.info("[STARTUP] MongoDB ping OK — existing sessions in DB: %d", count)
    except Exception as exc:
        import logging as _logging
        _logging.getLogger("neotriage.main").error(
            "[STARTUP] MongoDB connection FAILED: %s — DB writes will be skipped during this run.", exc
        )


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "neotriage-api"}