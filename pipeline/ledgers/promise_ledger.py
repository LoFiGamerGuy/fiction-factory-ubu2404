"""PromiseLedger — SQLite-backed bridge for the universal promise schema.

Wraps the universal promise_ledger JSON schema (schemas/universal/promise_ledger.schema.json)
into the append-only ledger pattern. Tracks within-book narrative promises.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.ledgers.base import BaseLedger


@dataclass
class PromiseEvent:
    event_id: str
    book_id: str
    promise_id: str
    timestamp: str
    event_type: str  # opened/progressed/resolved/force_resolved
    promise_type: str  # foreshadowing/chekhov_object/character_question/mystery_thread/...
    scene_id: str
    priority: str  # critical/high/medium/low
    description: str
    must_resolve_by: str | None = None
    resolution_note: str | None = None
    acceptable_resolutions: list[str] = field(default_factory=list)


class PromiseLedger(BaseLedger):
    def __init__(self, book_id: str, data_root: Path = Path("data")) -> None:
        db_path = data_root / book_id / "promise.db"
        super().__init__(db_path)

    def append(self, event: PromiseEvent) -> None:
        payload: dict[str, Any] = {
            "event_id": event.event_id,
            "book_id": event.book_id,
            "promise_id": event.promise_id,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "promise_type": event.promise_type,
            "scene_id": event.scene_id,
            "priority": event.priority,
            "description": event.description,
            "must_resolve_by": event.must_resolve_by,
            "resolution_note": event.resolution_note,
            "acceptable_resolutions": event.acceptable_resolutions,
        }
        self._append(event.event_id, payload)

    def open_promises(self) -> list[dict[str, Any]]:
        """Return latest event per promise_id that is not resolved."""
        latest: dict[str, dict[str, Any]] = {}
        for e in self._all_payloads():
            latest[e["promise_id"]] = e
        return [e for e in latest.values() if e["event_type"] not in {"resolved", "force_resolved"}]

    def overdue_promises(self, current_unit_id: str) -> list[dict[str, Any]]:
        """Return open promises where must_resolve_by < current_unit_id (lexicographic)."""
        return [
            p
            for p in self.open_promises()
            if p.get("must_resolve_by") and p["must_resolve_by"] < current_unit_id
        ]

    def summary(self) -> dict[str, int]:
        all_open = self.open_promises()
        return {
            "open": len(all_open),
            "critical_open": sum(1 for p in all_open if p.get("priority") == "critical"),
        }
