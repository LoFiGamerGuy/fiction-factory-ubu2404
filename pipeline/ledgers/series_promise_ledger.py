"""SeriesPromiseLedger — cross-book promise tracking for a series."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.ledgers.base import BaseLedger


@dataclass
class SeriesPromiseEvent:
    event_id: str
    series_id: str
    book_id: str
    scene_id: str
    promise_id: str
    timestamp: str
    promise_type: str  # series_thread/overarching_mystery/series_antagonist/character_arc_continuation/world_question  # noqa: E501
    status: str  # opened/progressed/resolved/broken
    description: str
    book_number: int
    cross_book_arc_id: str | None = None
    opened_book: int | None = None
    must_resolve_by_book: int | None = None


class SeriesPromiseLedger(BaseLedger):
    def __init__(self, series_id: str, data_root: Path = Path("data")) -> None:
        db_path = data_root / "series" / series_id / "series_promises.db"
        super().__init__(db_path)

    def append(self, event: SeriesPromiseEvent) -> None:
        payload: dict[str, Any] = {
            "event_id": event.event_id,
            "series_id": event.series_id,
            "book_id": event.book_id,
            "scene_id": event.scene_id,
            "promise_id": event.promise_id,
            "timestamp": event.timestamp,
            "promise_type": event.promise_type,
            "status": event.status,
            "description": event.description,
            "book_number": event.book_number,
            "cross_book_arc_id": event.cross_book_arc_id,
            "opened_book": event.opened_book,
            "must_resolve_by_book": event.must_resolve_by_book,
        }
        self._append(event.event_id, payload)

    def open_promises(self) -> list[dict[str, Any]]:
        """Return latest event per promise_id where status is not resolved."""
        latest: dict[str, dict[str, Any]] = {}
        for e in self._all_payloads():
            latest[e["promise_id"]] = e
        return [e for e in latest.values() if e["status"] not in {"resolved"}]

    def summary(self) -> dict[str, int]:
        events = self._all_payloads()
        latest: dict[str, str] = {}
        for e in events:
            latest[e["promise_id"]] = e["status"]
        statuses = list(latest.values())
        return {
            "open": sum(1 for s in statuses if s in {"opened", "progressed"}),
            "resolved": sum(1 for s in statuses if s == "resolved"),
            "broken": sum(1 for s in statuses if s == "broken"),
        }
