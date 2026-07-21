"""
db/__init__.py
==============
Public surface of the ``db`` package.

Import everything you need directly from here so internal module paths
can change without breaking callers.

Typical import pattern for teammates
-------------------------------------
::

    from db import (
        SessionState,
        InteractionLog,
        create_or_update_session,
        get_session,
        delete_session,
        log_interaction,
        get_logs,
    )
"""

from db.models import InteractionLog, SessionState
from db.repository import (
    create_or_update_session,
    delete_session,
    get_logs,
    get_session,
    log_interaction,
)

__all__ = [
    # Models
    "SessionState",
    "InteractionLog",
    # Repository functions
    "create_or_update_session",
    "get_session",
    "delete_session",
    "log_interaction",
    "get_logs",
]
