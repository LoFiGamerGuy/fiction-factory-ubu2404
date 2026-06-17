"""api/main.py — Author Dashboard FastAPI backend."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Literal

import yaml
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


def _book_summary_candidates(book_id: str) -> list[Path]:
    """Return likely book_run_summary.json paths for dashboard data-root layouts."""
    data_root = _data_root()
    candidates = [
        data_root / book_id / "book_run_summary.json",
        data_root / "books" / book_id / "book_run_summary.json",
        data_root / "data" / "books" / book_id / "book_run_summary.json",
    ]
    for base in (data_root, data_root.parent):
        series_root = base / "series"
        if not series_root.exists():
            continue
        candidates.extend(
            series_dir / "data" / "books" / book_id / "book_run_summary.json"
            for series_dir in sorted(series_root.iterdir())
            if series_dir.is_dir()
        )

    seen: set[Path] = set()
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _load_book_summary(book_id: str) -> tuple[Path, dict[str, Any]] | None:
    """Load the first matching book_run_summary.json for *book_id*."""
    for summary_path in _book_summary_candidates(book_id):
        if not summary_path.exists():
            continue
        loaded = json.loads(summary_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise HTTPException(
                status_code=500,
                detail=f"Invalid book_run_summary.json at {summary_path}",
            )
        return summary_path, loaded
    return None


def _ledger_data_root_for_book(book_id: str) -> Path:
    """Return the ledger root for book-level dashboard endpoints.

    Production full-book runs isolate ledgers under the run directory. When a
    summary advertises that location, use it so dashboard totals match the run
    artifact instead of any stale shared proof-run ledgers.
    """
    summary = _load_book_summary(book_id)
    if summary is not None:
        summary_path, loaded = summary
        raw = loaded.get("ledger_data_root")
        if raw:
            candidate = Path(str(raw))
            if not candidate.is_absolute():
                candidate = summary_path.parent / candidate
            if candidate.exists():
                return candidate
    return _data_root()


def _data_root() -> Path:
    """Return the ledger data root; tests may override app.state.data_root."""
    configured = getattr(app.state, "data_root", None)
    if configured is None:
        return Path(os.environ.get("FF_DASHBOARD_DATA_ROOT", "data"))
    return Path(configured)


def _run_dir(run_id: str) -> Path:
    return _data_root() / run_id


def _group_by_field(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        value = str(row.get(field, "unknown"))
        grouped.setdefault(value, []).append(row)
    return grouped


def _dedupe_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        key = str(row.get("event_id") or f"row-{index}-{json.dumps(row, sort_keys=True)}")
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _voice_profile_candidates(series_id: str) -> list[Path]:
    data_root = _data_root()
    candidates = [
        data_root / series_id / "profiles" / "voice_profile.yaml",
        data_root / "series" / series_id / "profiles" / "voice_profile.yaml",
        data_root.parent / "series" / series_id / "profiles" / "voice_profile.yaml",
    ]
    seen: set[Path] = set()
    unique: list[Path] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


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

    manager = LedgerManager(book_id, data_root=_ledger_data_root_for_book(book_id))
    try:
        dashboard = manager.get_dashboard_summary(book_id, "current")
        try:
            result: dict[str, Any] = dataclasses.asdict(dashboard)
        except TypeError:
            result = vars(dashboard)
        return result
    finally:
        manager.close()


@app.get("/books/{book_id}/summary")
async def get_book_summary(book_id: str) -> dict[str, Any]:
    """Return book_run_summary.json for *book_id* when available."""
    summary = _load_book_summary(book_id)
    if summary is not None:
        summary_path, loaded = summary
        result: dict[str, Any] = dict(loaded)
        result.setdefault("book_id", book_id)
        result.setdefault("summary_path", str(summary_path))
        result.setdefault("word_budget_status", {"enabled": False})
        result["summary_found"] = True
        return result
    return {
        "book_id": book_id,
        "summary_found": False,
        "word_budget_status": {"enabled": False},
    }


@app.get("/books/{book_id}/promises")
async def get_book_promises(book_id: str) -> dict[str, Any]:
    """Return within-book PromiseLedger events grouped by promise_id."""
    ledger_root = _ledger_data_root_for_book(book_id)
    db_path = ledger_root / book_id / "promise.db"
    if not db_path.exists():
        return {"book_id": book_id, "promises": {}}

    from pipeline.ledgers.promise_ledger import PromiseLedger  # noqa: PLC0415

    ledger = PromiseLedger(book_id, data_root=ledger_root)
    try:
        rows = ledger._all_payloads()
    finally:
        ledger.close()
    return {"book_id": book_id, "promises": _group_by_field(rows, "promise_id")}


@app.get("/books/{book_id}/intimacy")
async def get_book_intimacy(book_id: str) -> dict[str, Any]:
    """Return IntimacyEscalationLedger events for timeline display."""
    ledger_root = _ledger_data_root_for_book(book_id)
    db_path = ledger_root / book_id / "intimacy_escalation.db"
    if not db_path.exists():
        return {"book_id": book_id, "events": []}

    from pipeline.ledgers.intimacy_escalation_ledger import (  # noqa: PLC0415
        IntimacyEscalationLedger,
    )

    ledger = IntimacyEscalationLedger(book_id, data_root=ledger_root)
    try:
        rows = ledger._all_payloads()
    finally:
        ledger.close()
    return {"book_id": book_id, "events": rows}


@app.get("/books/{book_id}/metrics/history")
async def get_metrics_history(
    book_id: str,
    granularity: Literal["chapter", "scene", "beat"] = "chapter",
    metric: str | None = None,
) -> dict[str, Any]:
    """Return SQLite-backed book metrics history at chapter or scene granularity."""
    from pipeline.ledgers.ledger_manager import LedgerManager  # noqa: PLC0415

    manager = LedgerManager(book_id, data_root=_ledger_data_root_for_book(book_id))
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

    manager = LedgerManager(book_id, data_root=_ledger_data_root_for_book(book_id))
    try:
        return manager.get_character_metrics(char_id)
    finally:
        manager.close()


@app.get("/series/{series_id}/promises")
async def get_series_promises(series_id: str) -> dict[str, list[dict[str, Any]]]:
    """Return series promise events grouped by promise_id."""
    rows = _read_jsonl(_data_root() / series_id / "series_promises.jsonl")
    db_path = _data_root() / "series" / series_id / "series_promises.db"
    if db_path.exists():
        from pipeline.ledgers.series_promise_ledger import SeriesPromiseLedger  # noqa: PLC0415

        ledger = SeriesPromiseLedger(series_id, data_root=_data_root())
        try:
            rows.extend(ledger._all_payloads())
        finally:
            ledger.close()
    return _group_by_field(_dedupe_events(rows), "promise_id")


@app.get("/series/{series_id}/voice_calibration")
async def get_voice_calibration(series_id: str) -> dict[str, Any]:
    """Return voice profile calibration history for *series_id* when present."""
    for profile_path in _voice_profile_candidates(series_id):
        if not profile_path.exists():
            continue
        loaded = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise HTTPException(
                status_code=500,
                detail=f"Invalid voice_profile.yaml at {profile_path}",
            )
        raw: dict[str, Any] = {str(key): value for key, value in loaded.items()}
        history_raw = raw.get("calibration_history", [])
        history = history_raw if isinstance(history_raw, list) else []
        return {
            "series_id": series_id,
            "profile_found": True,
            "profile_path": str(profile_path),
            "profile_id": raw.get("profile_id"),
            "version": raw.get("version"),
            "display_name": raw.get("display_name"),
            "calibration_history": history,
        }
    return {"series_id": series_id, "profile_found": False, "calibration_history": []}


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
    return _read_jsonl(_ledger_data_root_for_book(book_id) / book_id / "quality_gate_history.jsonl")
