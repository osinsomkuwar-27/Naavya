"""
db/connection.py
================
Async MongoDB connection module for the Naavya / NeoTriage project.

Provides a single shared Motor client, the database handle, and named
collection references.  Every other module in the project should import
collections *from here* rather than constructing their own client.

Environment variables (loaded from backend/api/.env or the shell):
    MONGODB_URI      - full Atlas / MongoDB connection string (required)
    MONGODB_DB_NAME  - database name (required)

Usage
-----
    from db.connection import sessions_collection, interaction_logs_collection
"""

from __future__ import annotations

import os
import pathlib
from typing import Optional

from dotenv import load_dotenv
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)

# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------
# Resolve the .env relative to this file's location so the module works
# regardless of where `uvicorn` / pytest is launched from.
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / "backend" / "api" / ".env"

load_dotenv(dotenv_path=_ENV_PATH, override=False)  # shell vars take priority


def _require_env(key: str) -> str:
    """Return the value of *key* from the environment or raise a clear error."""
    value: Optional[str] = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"[db/connection.py] Required environment variable '{key}' is not set. "
            f"Add it to backend/api/.env or export it in your shell before starting "
            f"the server."
        )
    return value


# ---------------------------------------------------------------------------
# Client & database
# ---------------------------------------------------------------------------
_MONGODB_URI: str = _require_env("MONGODB_URI")
_MONGODB_DB_NAME: str = _require_env("MONGODB_DB_NAME")

#: Shared Motor client – one instance per process.
client: AsyncIOMotorClient = AsyncIOMotorClient(_MONGODB_URI)

#: The project database handle.
db: AsyncIOMotorDatabase = client[_MONGODB_DB_NAME]

# ---------------------------------------------------------------------------
# Named collection references
# ---------------------------------------------------------------------------
#: Stores per-conversation triage session state (SessionState documents).
sessions_collection: AsyncIOMotorCollection = db["sessions"]

#: Append-only log of every pipeline stage's input/output.
interaction_logs_collection: AsyncIOMotorCollection = db["interaction_logs"]