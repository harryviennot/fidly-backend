"""
Demo session event manager.

Simple in-memory event queue for pushing SSE updates to connected browsers.
Completely isolated from any future app event systems.
"""
import asyncio
from typing import Dict


# Maps session_token → asyncio.Queue
_demo_queues: Dict[str, asyncio.Queue] = {}


def register_session(session_token: str) -> asyncio.Queue:
    """Register an SSE connection for a session. Returns queue to wait on."""
    if session_token not in _demo_queues:
        _demo_queues[session_token] = asyncio.Queue()
    return _demo_queues[session_token]


def unregister_session(session_token: str):
    """Unregister when SSE connection closes."""
    _demo_queues.pop(session_token, None)


async def push_update(session_token: str, status: str, stamps: int):
    """Push an update to the SSE connection (if any)."""
    queue = _demo_queues.get(session_token)
    if queue:
        await queue.put({"status": status, "stamps": stamps})
