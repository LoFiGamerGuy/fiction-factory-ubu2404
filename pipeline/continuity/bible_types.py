"""Typed dataclasses for BibleSteward operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BibleEntity:
    entity_id: str
    entity_type: str  # character | location | object | event | relationship
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class BibleState:
    """Current in-memory representation of the series/book bible."""

    entities: dict[str, BibleEntity] = field(default_factory=dict)
    timeline_events: list[dict[str, Any]] = field(default_factory=list)
    content_hash: str = ""

    def entity(self, entity_id: str) -> BibleEntity | None:
        return self.entities.get(entity_id)


@dataclass
class BibleDelta:
    """A proposed change to apply to the bible."""

    delta_id: str
    entity_id: str
    entity_type: str
    operation: str  # upsert | delete | append_timeline
    new_attributes: dict[str, Any] = field(default_factory=dict)
    timeline_event: dict[str, Any] | None = None
    source_scene_id: str = ""


@dataclass
class ProposedDelta:
    """A validated-structure delta ready for contradiction checking."""

    original: BibleDelta
    proposed_id: str


@dataclass
class ValidationResult:
    valid: bool
    contradiction_type: str | None = None  # type_mismatch | timeline_violation | spatial |
    # capability | voice | taboo
    detail: str = ""
