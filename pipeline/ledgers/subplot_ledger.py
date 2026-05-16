"""SubplotLedger — tracks subplot state across scenes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.ledgers.base import BaseLedger


@dataclass
class SubplotEvent:
    event_id: str
    book_id: str
    scene_id: str
    subplot_id: str
    timestamp: str
    subplot_type: str  # romantic/professional/family/external/antagonist/thematic
    status: str  # opened/escalating/complicating/progressed/resolved/abandoned
    description: str
    priority: int
    opened_at_scene: str | None = None
    target_resolution_scene: str | None = None
    resolution_scene: str | None = None


class SubplotLedger(BaseLedger):
    def __init__(self, book_id: str, data_root: Path = Path("data")) -> None:
        db_path = data_root / book_id / "subplot.db"
        super().__init__(db_path)

    def append(self, event: SubplotEvent) -> None:
        payload: dict[str, Any] = {
            "event_id": event.event_id,
            "book_id": event.book_id,
            "scene_id": event.scene_id,
            "subplot_id": event.subplot_id,
            "timestamp": event.timestamp,
            "subplot_type": event.subplot_type,
            "status": event.status,
            "description": event.description,
            "priority": event.priority,
            "opened_at_scene": event.opened_at_scene,
            "target_resolution_scene": event.target_resolution_scene,
            "resolution_scene": event.resolution_scene,
        }
        self._append(event.event_id, payload)

    def summary(self) -> dict[str, int]:
        events = self._all_payloads()
        # Last status per subplot_id
        latest: dict[str, str] = {}
        for e in events:
            latest[e["subplot_id"]] = e["status"]
        statuses = list(latest.values())
        return {
            "open": sum(
                1 for s in statuses if s in {"opened", "escalating", "complicating", "progressed"}
            ),
            "resolved": sum(1 for s in statuses if s == "resolved"),
            "abandoned": sum(1 for s in statuses if s == "abandoned"),
        }
