"""ReaderInformationStateLedger — tracks what reader knows vs. characters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.ledgers.base import BaseLedger


@dataclass
class RevelationEvent:
    event_id: str
    book_id: str
    scene_id: str
    fact_id: str
    timestamp: str
    revelation_type: str  # dramatic_irony/revelation/red_herring/confirmation/misdirect
    fact_description: str
    known_by_reader: bool
    known_by_characters: list[str] = field(default_factory=list)
    irony_type: str = "none"  # dramatic/tragic/situational/none
    chapter_number: int | None = None
    notes: str = ""


class ReaderInformationStateLedger(BaseLedger):
    def __init__(self, book_id: str, data_root: Path = Path("data")) -> None:
        db_path = data_root / book_id / "reader_information_state.db"
        super().__init__(db_path)

    def append(self, event: RevelationEvent) -> None:
        payload: dict[str, Any] = {
            "event_id": event.event_id,
            "book_id": event.book_id,
            "scene_id": event.scene_id,
            "fact_id": event.fact_id,
            "timestamp": event.timestamp,
            "revelation_type": event.revelation_type,
            "fact_description": event.fact_description,
            "known_by_reader": event.known_by_reader,
            "known_by_characters": event.known_by_characters,
            "irony_type": event.irony_type,
            "chapter_number": event.chapter_number,
            "notes": event.notes,
        }
        self._append(event.event_id, payload)

    def summary(self) -> dict[str, int]:
        """Return counts: known_by_reader, unknown_by_reader, active_irony."""
        events = self._all_payloads()
        known = sum(1 for e in events if e.get("known_by_reader"))
        unknown = len(events) - known
        irony = sum(1 for e in events if e.get("irony_type", "none") != "none")
        return {"known_by_reader": known, "unknown_by_reader": unknown, "active_irony": irony}
