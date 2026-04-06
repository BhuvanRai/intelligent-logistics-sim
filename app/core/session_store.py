"""
In-memory session store.

Keeps per-session episode state so that multiple concurrent agents
(or the inference script running sequential tasks) share no state.

For production you would back this with Redis; for the competition
in-memory is sufficient (single Gunicorn worker).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional


                                                          
_SESSIONS: Dict[str, Dict[str, Any]] = {}


def new_session() -> str:
    """Create and register a fresh session, returning the session_id."""
    sid = str(uuid.uuid4())
    _SESSIONS[sid] = {}
    return sid


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    return _SESSIONS.get(session_id)


def set_session(session_id: str, state: Dict[str, Any]) -> None:
    _SESSIONS[session_id] = state


def delete_session(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)


def list_sessions() -> list[str]:
    return list(_SESSIONS.keys())
