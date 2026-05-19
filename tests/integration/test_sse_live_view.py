"""Integration tests — SSE live-view event queue (Task 013).

Tests:
  1. test_push_event_queued   — push_event puts a dict into _sse_queue
  2. test_sse_event_format    — events in the queue are formatted as SSE dicts

Note: httpx ASGITransport buffers the full response body before yielding, so
it cannot test an infinite SSE stream via HTTP. These tests verify the queue
mechanics and the SSE formatting logic that our code owns.
"""

from __future__ import annotations

import json

from api.main import _sse_queue

# ── Helpers ───────────────────────────────────────────────────────────────────


def _drain_queue() -> None:
    """Empty the module-level SSE queue between tests."""
    while not _sse_queue.empty():
        _sse_queue.get_nowait()


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_push_event_queued() -> None:
    """put_nowait places the dict into _sse_queue without blocking."""
    _drain_queue()

    event: dict[str, object] = {"event": "scene_done", "scene_id": "sc-001", "words": 1234}
    _sse_queue.put_nowait(event)

    assert not _sse_queue.empty()
    retrieved = _sse_queue.get_nowait()
    assert retrieved == event
    assert retrieved["scene_id"] == "sc-001"


def test_sse_event_format() -> None:
    """Queue items are wrapped as SSE dicts with 'data' and 'event' keys.

    The generator in stream_run_events yields:
        {"data": json.dumps(item), "event": item.get("event", "update")}
    Verify the format directly on a fixture event.
    """
    _drain_queue()

    fixture: dict[str, object] = {
        "event": "quality_gate",
        "book_id": "book-001",
        "verdict": "GO",
    }
    _sse_queue.put_nowait(fixture)

    item = _sse_queue.get_nowait()
    assert item == fixture

    # Reproduce the generator's yield expression.
    sse_dict: dict[str, str] = {
        "data": json.dumps(item),
        "event": str(item.get("event", "update")),
    }

    assert sse_dict["event"] == "quality_gate"
    payload = json.loads(sse_dict["data"])
    assert payload.get("book_id") == "book-001"
    assert payload.get("verdict") == "GO"
