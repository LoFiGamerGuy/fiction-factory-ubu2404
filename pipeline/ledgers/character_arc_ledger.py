"""CharacterArcLedger — arc state snapshot per character per scene."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.ledgers.base import BaseLedger


@dataclass
class CharacterArcEvent:
    event_id: str
    book_id: str
    scene_id: str
    character_id: str
    timestamp: str
    arc_phase: str  # opening/wound_open/processing/wound_healing/resolved/not_started
    wound_state: str
    belief_current: str
    belief_true: str
    relationship_states: dict[str, dict[str, str]] = field(default_factory=dict)
    arc_beat_delivered: str | None = None


class CharacterArcLedger(BaseLedger):
    def __init__(self, book_id: str, data_root: Path = Path("data")) -> None:
        db_path = data_root / book_id / "character_arc.db"
        super().__init__(db_path)

    def append(self, event: CharacterArcEvent) -> None:
        payload: dict[str, Any] = {
            "event_id": event.event_id,
            "book_id": event.book_id,
            "scene_id": event.scene_id,
            "character_id": event.character_id,
            "timestamp": event.timestamp,
            "arc_phase": event.arc_phase,
            "wound_state": event.wound_state,
            "belief_state": {
                "current": event.belief_current,
                "true": event.belief_true,
            },
            "relationship_states": event.relationship_states,
            "arc_beat_delivered": event.arc_beat_delivered,
        }
        self._append(event.event_id, payload)

    def get_arc_position(self, character_id: str) -> str | None:
        """Return the most recent arc_phase for a character, or None if no events."""
        events = self._payloads_where("character_id", character_id)
        if not events:
            return None
        return str(events[-1]["arc_phase"])

    def get_character_history(self, character_id: str) -> list[dict[str, Any]]:
        return self._payloads_where("character_id", character_id)
