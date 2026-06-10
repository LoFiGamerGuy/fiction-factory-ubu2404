"""File-backed dashboard event helpers for local Author Dashboard runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    """Return current UTC timestamp as an ISO string."""
    return datetime.now(UTC).isoformat()


def write_run_state(data_root: Path, run_id: str, payload: dict[str, Any]) -> None:
    """Write latest run state for `GET /runs/{run_id}/status`."""
    path = data_root / run_id / "run_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def append_run_event(data_root: Path, run_id: str, payload: dict[str, Any]) -> None:
    """Append one event for `GET /runs/{run_id}/stream` replay/streaming."""
    _append_jsonl(data_root / run_id / "dashboard_events.jsonl", payload)


def append_quality_gate_event(data_root: Path, book_id: str, payload: dict[str, Any]) -> None:
    """Append one quality-gate event for dashboard historical/live feed."""
    _append_jsonl(data_root / book_id / "quality_gate_history.jsonl", payload)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")
