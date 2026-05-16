"""BibleTracker — SQLite-backed continuity event log.

Thin wrapper over the SQLite ledger pattern for bible/continuity events.
Full ContinuityModel validation lives in pipeline/continuity/; this ledger
records the event stream of propose_delta / commit_delta / contradiction
events so the Author Dashboard can surface continuity health at a glance.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.ledgers.base import BaseLedger


@dataclass
class ContinuityEvent:
    event_id: str
    book_id: str
    scene_id: str
    timestamp: str
    fact_type: str  # character/location/object/timeline/relationship/concept
    entity_id: str
    operation: str  # propose_delta/commit_delta/contradiction_detected/contradiction_resolved
    description: str
    contradiction_type: str | None = None  # type_mismatch/timeline_violation/...
    resolved: bool = False


class BibleTracker(BaseLedger):
    def __init__(self, book_id: str, data_root: Path = Path("data")) -> None:
        db_path = data_root / book_id / "bible_tracker.db"
        super().__init__(db_path)

    def append(self, event: ContinuityEvent) -> None:
        payload: dict[str, Any] = {
            "event_id": event.event_id,
            "book_id": event.book_id,
            "scene_id": event.scene_id,
            "timestamp": event.timestamp,
            "fact_type": event.fact_type,
            "entity_id": event.entity_id,
            "operation": event.operation,
            "description": event.description,
            "contradiction_type": event.contradiction_type,
            "resolved": event.resolved,
        }
        self._append(event.event_id, payload)

    def unresolved_contradictions(self) -> list[dict[str, Any]]:
        return [
            e
            for e in self._all_payloads()
            if e["operation"] == "contradiction_detected" and not e.get("resolved")
        ]

    def summary(self) -> dict[str, int]:
        events = self._all_payloads()
        contradictions = [e for e in events if e["operation"] == "contradiction_detected"]
        unresolved = [e for e in contradictions if not e.get("resolved")]
        return {
            "total_deltas": sum(1 for e in events if "delta" in e["operation"]),
            "contradictions": len(contradictions),
            "unresolved_contradictions": len(unresolved),
        }
