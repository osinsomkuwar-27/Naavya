# db — Naavya Database Layer
 
> **Stack**: FastAPI · Motor (async) · MongoDB Atlas · Pydantic v2  
> **Location**: `db/` at the project root (importable by all modules)

---

## ⚠️ Privacy Contract — Read First

This layer is intentionally **PII-free**.  
The following data must **never** appear in any document stored through this layer:

| Prohibited data | Examples |
|---|---|
| Names | Mother, husband, ASHA worker |
| Contact info | Phone number, WhatsApp ID |
| Location | Village, district, address |
| Demographics | Age, caste, religion |

The only identifier stored is **`conversation_id`** — an opaque UUID that carries no personal meaning on its own.

---

## Setup

### 1. Install dependencies

Add to your `requirements.txt` (or install directly):

```
motor>=3.3
pymongo>=4.6
python-dotenv>=1.0
pydantic>=2.0
```

### 2. Environment variables

`connection.py` auto-loads `backend/api/.env`.  
Make sure the file contains:

```dotenv
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?appName=<App>
MONGODB_DB_NAME=Naavya
```

> **Never commit credentials.** `.env` is already in `.gitignore`.

---

## How to import

Use the top-level package for all imports:

```python
from db import (
    SessionState,
    InteractionLog,
    create_or_update_session,
    get_session,
    delete_session,
    log_interaction,
    get_logs,
)
```

Or import from specific sub-modules if you prefer:

```python
from db.repository import log_interaction, get_session
from db.models import InteractionLog, SessionState
```

---

## API Reference

### `create_or_update_session(state: SessionState) -> None`

Upsert a session document.  Call this whenever the conversation state changes.

```python
from db import create_or_update_session, SessionState

await create_or_update_session(
    SessionState(
        conversation_id=conv_id,        # your UUID
        status="intake",
        extracted_signs={"fast_breathing": True},
    )
)
```

`created_at` is set **only on the first insert** — subsequent calls update `updated_at` and the mutable fields.

---

### `get_session(conversation_id: str) -> SessionState | None`

Fetch the current state of a session.  Returns `None` if no session exists yet.

```python
from db import get_session

session = await get_session(conv_id)
if session is None:
    # No prior state — start fresh intake
    ...
else:
    print(session.status, session.risk_level)
```

---

### `delete_session(conversation_id: str) -> bool`

Remove a session once it has expired or been resolved.  
Returns `True` if a document was deleted, `False` if not found.

```python
from db import delete_session

was_deleted = await delete_session(conv_id)
```

---

### `log_interaction(entry: InteractionLog) -> None`

Append a pipeline-stage record to the audit log.  
**Logs are write-once — never modified.**

```python
from db import log_interaction, InteractionLog

await log_interaction(
    InteractionLog(
        conversation_id=conv_id,
        stage="risk_combination",          # your stage name
        input_data={"fast_breathing": True, "poor_feeding": True},
        output_data={"urgency": "refer_now"},
    )
)
```

Valid `stage` values: `"asr"` · `"intake"` · `"disambiguation"` · `"risk_combination"` · `"escalation"`

---

### `get_logs(conversation_id, stage=None, limit=100) -> list[InteractionLog]`

Retrieve audit logs for a conversation, optionally filtered by stage.

```python
from db import get_logs

# All logs for a session (oldest first)
all_logs = await get_logs(conv_id)

# Only the risk_combination logs
risk_logs = await get_logs(conv_id, stage="risk_combination")
```

---

## Team usage guide

### Soham — `backend/api/routes/assess.py`

After each pipeline stage, log what happened and upsert the session:

```python
from db import (
    SessionState, InteractionLog,
    create_or_update_session, log_interaction,
)

# After intake completes
await log_interaction(InteractionLog(
    conversation_id=household_id,
    stage="intake",
    input_data=transcript_text,
    output_data=intake_dict,
))

await create_or_update_session(SessionState(
    conversation_id=household_id,
    status="intake",
    extracted_signs=intake_dict.get("clear_signs", {}),
))
```

### Shreeja — `agents/disambiguation/` · `agents/escalation/`

Read existing session state so your agent knows what's already confirmed, then log your output:

```python
from db import get_session, create_or_update_session, log_interaction, InteractionLog

# Read
session = await get_session(conv_id)
confirmed = session.extracted_signs if session else {}

# Write your stage output
await log_interaction(InteractionLog(
    conversation_id=conv_id,
    stage="disambiguation",
    input_data={"vague_signs": vague_list, "question_asked": question},
    output_data={"resolved_signs": resolved},
))

# Update state
await create_or_update_session(SessionState(
    conversation_id=conv_id,
    status="disambiguating",
    extracted_signs={**confirmed, **resolved},
    pending_question=question,
))
```

### Kshitij — `agents/risk_combination/`

Fetch the session, run classification, then persist the risk level:

```python
from db import get_session, create_or_update_session, log_interaction, InteractionLog, SessionState

session = await get_session(conv_id)
signs = session.extracted_signs if session else {}

# ... run your risk logic ...
risk_level = risk_agent.classify(signs)

await log_interaction(InteractionLog(
    conversation_id=conv_id,
    stage="risk_combination",
    input_data=signs,
    output_data={"risk_level": risk_level},
))

await create_or_update_session(SessionState(
    conversation_id=conv_id,
    status="classified",
    extracted_signs=signs,
    risk_level=risk_level,
))
```

---

## Adding a new collection

1. Declare the collection reference in [`connection.py`](connection.py):
   ```python
   my_new_collection: AsyncIOMotorCollection = db["my_new_collection"]
   ```
2. Add the corresponding Pydantic model in [`models.py`](models.py).
3. Add repository functions in [`repository.py`](repository.py) following the existing pattern.
4. Re-export from [`__init__.py`](__init__.py).

---

## Error handling

All repository functions wrap `PyMongoError` in a `RuntimeError` with a
descriptive message and log the original traceback at `ERROR` level.
Callers can `try / except RuntimeError` to handle database failures gracefully.