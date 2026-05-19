"""api/main.py — Author Dashboard FastAPI backend."""

from __future__ import annotations

import asyncio
import dataclasses
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse  # noqa: F401 — kept for type completeness
from sse_starlette.sse import EventSourceResponse

app = FastAPI(title="Fiction-Factory Author Dashboard", version="0.1.0")

# Module-level SSE event queue — job_runner pushes events from sync context via push_event().
_sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()


def push_event(event: dict[str, Any]) -> None:
    """Push an event into the SSE queue from a synchronous context."""
    asyncio.get_event_loop().call_soon_threadsafe(_sse_queue.put_nowait, event)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a .jsonl file and return parsed rows; returns [] if file absent."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/runs/{run_id}/status")
async def get_run_status(run_id: str) -> dict[str, Any]:
    """Return the run_state.json for *run_id*, or a sentinel if absent."""
    state_file = Path("data") / run_id / "run_state.json"
    if state_file.exists():
        raw: dict[str, Any] = json.loads(state_file.read_text(encoding="utf-8"))
        return raw
    return {"run_id": run_id, "status": "no_active_run"}


@app.get("/runs/{run_id}/stream")
async def stream_run_events(run_id: str, request: Request) -> EventSourceResponse:
    """SSE endpoint — streams events from the module-level _sse_queue."""

    async def _generator() -> AsyncGenerator[dict[str, str], None]:
        while True:
            if await request.is_disconnected():
                break
            try:
                item: dict[str, Any] = await asyncio.wait_for(_sse_queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            yield {
                "data": json.dumps(item),
                "event": str(item.get("event", "update")),
            }

    return EventSourceResponse(_generator())


@app.get("/books/{book_id}/ledgers")
async def get_ledgers(book_id: str) -> dict[str, Any]:
    """Return the current AuthorDashboard snapshot for *book_id*."""
    # Deferred import — allows tests to mock without ledger data on disk.
    from pipeline.ledgers.ledger_manager import LedgerManager  # noqa: PLC0415

    manager = LedgerManager(book_id, data_root=Path("data"))
    dashboard = manager.get_dashboard_summary(book_id, "current")
    try:
        result: dict[str, Any] = dataclasses.asdict(dashboard)
    except TypeError:
        result = vars(dashboard)
    return result


@app.get("/books/{book_id}/metrics/history")
async def get_metrics_history(book_id: str) -> dict[str, list[dict[str, Any]]]:
    """Return book_metrics events grouped by chapter_id."""
    rows = _read_jsonl(Path("data") / book_id / "book_metrics.jsonl")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        chapter_id = str(row.get("chapter_id", "unknown"))
        grouped.setdefault(chapter_id, []).append(row)
    return grouped


@app.get("/series/{series_id}/promises")
async def get_series_promises(series_id: str) -> dict[str, list[dict[str, Any]]]:
    """Return series promise events grouped by promise_id."""
    rows = _read_jsonl(Path("data") / series_id / "series_promises.jsonl")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        promise_id = str(row.get("promise_id", "unknown"))
        grouped.setdefault(promise_id, []).append(row)
    return grouped


@app.get("/series/{series_id}/evoskill")
async def get_evoskill(series_id: str) -> list[dict[str, Any]]:
    """Return EvoSkill markdown files for *series_id*."""
    skills_dir = Path("data") / series_id / "skills"
    if not skills_dir.exists():
        return []
    result: list[dict[str, Any]] = []
    for md_file in sorted(skills_dir.glob("*.md")):
        result.append(
            {
                "skill_id": md_file.stem,
                "content": md_file.read_text(encoding="utf-8"),
            }
        )
    return result


@app.get("/books/{book_id}/quality_gates")
async def get_quality_gates(book_id: str) -> list[dict[str, Any]]:
    """Return all quality gate history events for *book_id*."""
    return _read_jsonl(Path("data") / book_id / "quality_gate_history.jsonl")
