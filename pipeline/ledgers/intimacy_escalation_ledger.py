"""IntimacyEscalationLedger — tracks heat escalation between character pairs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.ledgers.base import BaseLedger

# Ordered escalation ladder — each step must come after the previous.
_ESCALATION_ORDER = [
    "first_touch",
    "first_charged_moment",
    "first_kiss",
    "first_explicit",
    "escalation_peak",
    "explicit_scene",
    "post_explicit_emotional_beat",
]

# Non-escalation events (separation/reconciliation don't consume a ladder slot)
_NON_ESCALATION = {"separation", "reconciliation"}


@dataclass
class IntimacyEvent:
    event_id: str
    book_id: str
    scene_id: str
    pair_id: str
    character_pair: list[str]
    chapter_number: int
    timestamp: str
    event_type: str
    heat_level: str  # sweet/sensual/steamy/erotic
    description: str
    consent_present: bool | None = None


class IntimacyEscalationLedger(BaseLedger):
    def __init__(self, book_id: str, data_root: Path = Path("data")) -> None:
        db_path = data_root / book_id / "intimacy_escalation.db"
        super().__init__(db_path)

    def append(self, event: IntimacyEvent) -> None:
        payload: dict[str, Any] = {
            "event_id": event.event_id,
            "book_id": event.book_id,
            "scene_id": event.scene_id,
            "pair_id": event.pair_id,
            "character_pair": event.character_pair,
            "chapter_number": event.chapter_number,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "heat_level": event.heat_level,
            "description": event.description,
            "consent_present": event.consent_present,
        }
        self._append(event.event_id, payload)

    def get_pair_history(self, pair_id: str) -> list[dict[str, Any]]:
        return self._payloads_where("pair_id", pair_id)

    def last_act_type(self, pair_id: str) -> str | None:
        events = self.get_pair_history(pair_id)
        if not events:
            return None
        return str(events[-1]["event_type"])

    def validate_escalation(self, pair_id: str, proposed_act: str) -> bool:
        """Return True if proposed_act is a valid escalation from the last recorded act.

        Non-escalation events (separation, reconciliation) are always allowed.
        Ladder events must appear in order; repeating the same rung is rejected.
        """
        if proposed_act in _NON_ESCALATION:
            return True

        last = self.last_act_type(pair_id)
        if last is None or last in _NON_ESCALATION:
            # First escalation event — must be the lowest rung
            return proposed_act == _ESCALATION_ORDER[0]

        try:
            last_idx = _ESCALATION_ORDER.index(last)
            prop_idx = _ESCALATION_ORDER.index(proposed_act)
        except ValueError:
            return False

        # Sequential steps only — must advance by exactly one rung
        return prop_idx == last_idx + 1
