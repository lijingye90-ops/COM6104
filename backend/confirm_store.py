"""Per-conversation confirmation gates for the ask_user tool."""
from __future__ import annotations

import asyncio
from typing import Optional

# conversation_id -> (event, decision)
_pending: dict[str, tuple[asyncio.Event, Optional[bool]]] = {}


def arm(conversation_id: str) -> asyncio.Event:
    """Create a gate for a conversation. Must be called before waiting."""
    event = asyncio.Event()
    _pending[conversation_id] = (event, None)
    return event


def resolve(conversation_id: str, confirmed: bool) -> bool:
    """Called by POST /api/chat/confirm. Returns False if no gate was armed."""
    if conversation_id not in _pending:
        return False
    event, _ = _pending[conversation_id]
    _pending[conversation_id] = (event, confirmed)
    event.set()
    return True


def take(conversation_id: str) -> Optional[bool]:
    """Pop the decision after the event fires. Returns None if timed out."""
    entry = _pending.pop(conversation_id, None)
    if entry is None:
        return None
    _, decision = entry
    return decision


def is_pending(conversation_id: str) -> bool:
    return conversation_id in _pending
