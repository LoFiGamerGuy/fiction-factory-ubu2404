"""api/main.py — Author Dashboard FastAPI backend."""

from __future__ import annotations

import asyncio
import dataclasses
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
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


def _data_root() -> Path:
    """Return the ledger data root; tests may override app.state.data_root."""
    configured = getattr(app.state, "data_root", None)
    if configured is None:
        return Path("data")
    return Path(configured)


def _run_dir(run_id: str) -> Path:
    return _data_root() / run_id


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/runs/{run_id}/status")
async def get_run_status(run_id: str) -> dict[str, Any]:
    """Return the run_state.json for *run_id*, or a sentinel if absent."""
    state_file = _run_dir(run_id) / "run_state.json"
    if state_file.exists():
        raw: dict[str, Any] = json.loads(state_file.read_text(encoding="utf-8"))
        return raw
    return {"run_id": run_id, "status": "no_active_run"}


@app.get("/runs/{run_id}/stream")
async def stream_run_events(run_id: str, request: Request) -> EventSourceResponse:
    """SSE endpoint — streams persisted run events plus in-process queue events."""

    async def _generator() -> AsyncGenerator[dict[str, str], None]:
        events_file = _run_dir(run_id) / "dashboard_events.jsonl"
        seen_events = 0
        while True:
            if await request.is_disconnected():
                break
            persisted = _read_jsonl(events_file)
            for item in persisted[seen_events:]:
                yield {
                    "data": json.dumps(item),
                    "event": str(item.get("event", "update")),
                }
            seen_events = len(persisted)
            try:
                queued_item: dict[str, Any] = await asyncio.wait_for(_sse_queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            if str(queued_item.get("run_id", run_id)) != run_id:
                continue
            yield {
                "data": json.dumps(queued_item),
                "event": str(queued_item.get("event", "update")),
            }

    return EventSourceResponse(_generator())


@app.get("/books/{book_id}/ledgers")
async def get_ledgers(book_id: str) -> dict[str, Any]:
    """Return the current AuthorDashboard snapshot for *book_id*."""
    # Deferred import — allows tests to mock without ledger data on disk.
    from pipeline.ledgers.ledger_manager import LedgerManager  # noqa: PLC0415

    manager = LedgerManager(book_id, data_root=_data_root())
    try:
        dashboard = manager.get_dashboard_summary(book_id, "current")
        try:
            result: dict[str, Any] = dataclasses.asdict(dashboard)
        except TypeError:
            result = vars(dashboard)
        return result
    finally:
        manager.close()


@app.get("/books/{book_id}/metrics/history")
async def get_metrics_history(
    book_id: str,
    granularity: Literal["chapter", "scene", "beat"] = "chapter",
    metric: str | None = None,
) -> dict[str, Any]:
    """Return SQLite-backed book metrics history at chapter or scene granularity."""
    from pipeline.ledgers.ledger_manager import LedgerManager  # noqa: PLC0415

    manager = LedgerManager(book_id, data_root=_data_root())
    try:
        return manager.get_metrics_history(granularity=granularity, metric=metric)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        manager.close()


@app.get("/books/{book_id}/characters/{char_id}/metrics")
async def get_character_metrics(book_id: str, char_id: str) -> dict[str, Any]:
    """Return SQLite-backed per-scene character metrics for one character."""
    from pipeline.ledgers.ledger_manager import LedgerManager  # noqa: PLC0415

    manager = LedgerManager(book_id, data_root=_data_root())
    try:
        return manager.get_character_metrics(char_id)
    finally:
        manager.close()


@app.get("/series/{series_id}/promises")
async def get_series_promises(series_id: str) -> dict[str, list[dict[str, Any]]]:
    """Return series promise events grouped by promise_id."""
    rows = _read_jsonl(_data_root() / series_id / "series_promises.jsonl")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        promise_id = str(row.get("promise_id", "unknown"))
        grouped.setdefault(promise_id, []).append(row)
    return grouped


@app.get("/series/{series_id}/evoskill")
async def get_evoskill(series_id: str) -> list[dict[str, Any]]:
    """Return EvoSkill markdown files for *series_id*."""
    skills_dir = _data_root() / series_id / "skills"
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
    return _read_jsonl(_data_root() / book_id / "quality_gate_history.jsonl")
