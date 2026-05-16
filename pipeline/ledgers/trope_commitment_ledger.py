"""TropeCommitmentLedger — tracks trope activation and required beat delivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.ledgers.base import BaseLedger


@dataclass
class RequiredBeat:
    beat_id: str
    description: str
    target_chapter: int
    status: str = "pending"  # pending/fulfilled/overdue


@dataclass
class TropeEvent:
    event_id: str
    book_id: str
    scene_id: str
    trope_id: str
    trope_name: str
    genre_module: str
    timestamp: str
    status: str  # activated/beat_delivered/partially_resolved/resolved/overdue
    activated_at_scene: str | None = None
    required_beats: list[RequiredBeat] = field(default_factory=list)


class TropeCommitmentLedger(BaseLedger):
    def __init__(self, book_id: str, data_root: Path = Path("data")) -> None:
        db_path = data_root / book_id / "trope_commitment.db"
        super().__init__(db_path)

    def append(self, event: TropeEvent) -> None:
        payload: dict[str, Any] = {
            "event_id": event.event_id,
            "book_id": event.book_id,
            "scene_id": event.scene_id,
            "trope_id": event.trope_id,
            "trope_name": event.trope_name,
            "genre_module": event.genre_module,
            "timestamp": event.timestamp,
            "status": event.status,
            "activated_at_scene": event.activated_at_scene,
            "required_beats": [
                {
                    "beat_id": b.beat_id,
                    "description": b.description,
                    "target_chapter": b.target_chapter,
                    "status": b.status,
                }
                for b in event.required_beats
            ],
        }
        self._append(event.event_id, payload)

    def pending_beats(self) -> list[dict[str, Any]]:
        """Return all required_beats with status pending or overdue across all tropes."""
        result = []
        for e in self._all_payloads():
            for b in e.get("required_beats", []):
                if b["status"] in {"pending", "overdue"}:
                    result.append({**b, "trope_id": e["trope_id"], "trope_name": e["trope_name"]})
        return result

    def summary(self) -> dict[str, int]:
        beats = self.pending_beats()
        return {
            "pending": sum(1 for b in beats if b["status"] == "pending"),
            "overdue": sum(1 for b in beats if b["status"] == "overdue"),
        }
