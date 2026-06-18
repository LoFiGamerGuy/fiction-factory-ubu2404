"""Deterministic narrative event extraction for runtime ledgers."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pipeline.core.job_context import JobContext
from pipeline.ledgers.character_arc_ledger import CharacterArcEvent
from pipeline.ledgers.intimacy_escalation_ledger import IntimacyEvent
from pipeline.ledgers.promise_ledger import PromiseEvent
from pipeline.ledgers.reader_information_state_ledger import RevelationEvent
from pipeline.ledgers.subplot_ledger import SubplotEvent
from pipeline.ledgers.trope_commitment_ledger import RequiredBeat, TropeEvent


@dataclass(frozen=True)
class NarrativeExtraction:
    scene_type: str = "action"
    character_arc_events: list[CharacterArcEvent] = field(default_factory=list)
    intimacy_events: list[IntimacyEvent] = field(default_factory=list)
    revelation_events: list[RevelationEvent] = field(default_factory=list)
    subplot_events: list[SubplotEvent] = field(default_factory=list)
    trope_events: list[TropeEvent] = field(default_factory=list)
    promise_events: list[PromiseEvent] = field(default_factory=list)


_NAME_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")
_QUESTION_RE = re.compile(r"\?")
_INTIMACY_RE = re.compile(
    r"\b(kiss(?:ed)?|touch(?:ed)?|hand|hands|desire|heat|held|embrace|mouth|skin)\b", re.IGNORECASE
)
_REVELATION_RE = re.compile(
    r"\b(realized|revealed|discovered|learned|understood|truth|secret|confessed|admitted)\b",
    re.IGNORECASE,
)
_PROFESSIONAL_RE = re.compile(
    r"\b(contract|permit|budget|renovation|repair|foundation|inspection|architect|builder|restoration|house|inn|project)\b",
    re.IGNORECASE,
)
_FAMILY_RE = re.compile(
    r"\b(family|mother|father|sister|brother|daughter|son|parent|child)\b", re.IGNORECASE
)
_RESOLUTION_RE = re.compile(
    r"\b(resolved|decided|chose|finished|forgave|agreed|settled|answered)\b", re.IGNORECASE
)
_SECOND_CHANCE_RE = re.compile(
    r"\b(second chance|almost married|ten years|ex\b|former fiance|old love)\b", re.IGNORECASE
)
_EXCLUDE_NAMES = {
    "The",
    "She",
    "He",
    "They",
    "This",
    "That",
    "There",
    "When",
    "After",
    "Before",
    "Chapter",
    "Scene",
}


def extract_narrative_events(
    *,
    job_context: JobContext,
    text: str,
    metrics: Mapping[str, float],
    character_metrics: Mapping[str, Any],
    timestamp: str,
) -> NarrativeExtraction:
    """Extract lightweight narrative ledger events from finalized scene text."""
    characters = _detect_characters(text, character_metrics)
    scene_type = classify_scene_type(
        text=text,
        metrics=metrics,
        scene_brief=job_context.scene_brief,
        heat_level=job_context.heat_level,
    )

    return NarrativeExtraction(
        scene_type=scene_type,
        character_arc_events=_character_arc_events(job_context, characters, timestamp),
        intimacy_events=_intimacy_events(job_context, text, characters, timestamp),
        revelation_events=_revelation_events(job_context, text, characters, timestamp),
        subplot_events=_subplot_events(job_context, text, timestamp),
        trope_events=_trope_events(job_context, text, timestamp),
        promise_events=_promise_events(job_context, text, timestamp),
    )


def classify_scene_type(
    *,
    text: str,
    metrics: Mapping[str, float],
    scene_brief: str,
    heat_level: int,
) -> str:
    """Infer one of the supported SceneRhythmLedger scene types."""
    brief = scene_brief.lower()
    if heat_level >= 4 or re.search(r"\b(sex|explicit|erotic|naked)\b", text, re.IGNORECASE):
        return "sex"
    if "aftermath" in brief or "resolution" in brief:
        return "aftermath"
    dialogue_ratio = float(metrics.get("dialogue_ratio", 0.0))
    interiority = float(metrics.get("interiority_pct", 0.0))
    action = float(metrics.get("action_pct", 0.0))
    if dialogue_ratio >= 0.45:
        return "dialogue"
    if interiority >= 0.28 and dialogue_ratio < 0.35:
        return "introspection"
    if action >= 0.35:
        return "action"
    if "setup" in brief or "opening" in brief:
        return "setup"
    return "transition"


def _character_arc_events(
    job_context: JobContext,
    characters: list[str],
    timestamp: str,
) -> list[CharacterArcEvent]:
    events: list[CharacterArcEvent] = []
    chapter = int(job_context.chapter_id)
    phase = _arc_phase(chapter)
    for character_id in characters[:3]:
        others = [other for other in characters[:3] if other != character_id]
        events.append(
            CharacterArcEvent(
                event_id=_event_id("arc"),
                book_id=job_context.book_id,
                scene_id=job_context.scene_id,
                character_id=character_id,
                timestamp=timestamp,
                arc_phase=phase,
                wound_state="active" if phase in {"wound_open", "processing"} else "integrating",
                belief_current="guarded trust",
                belief_true="trust can be rebuilt through action",
                relationship_states={other: {"status": "active_scene_partner"} for other in others},
                arc_beat_delivered=f"deterministic_{phase}",
            )
        )
    return events


def _intimacy_events(
    job_context: JobContext,
    text: str,
    characters: list[str],
    timestamp: str,
) -> list[IntimacyEvent]:
    if len(characters) < 2 or not _INTIMACY_RE.search(text):
        return []
    pair = sorted(characters[:2])
    event_type = _intimacy_type(text, int(job_context.chapter_id))
    return [
        IntimacyEvent(
            event_id=_event_id("intimacy"),
            book_id=job_context.book_id,
            scene_id=job_context.scene_id,
            pair_id="__".join(pair),
            character_pair=pair,
            chapter_number=int(job_context.chapter_id),
            timestamp=timestamp,
            event_type=event_type,
            heat_level=_heat_label(job_context.heat_level),
            description=f"Deterministic intimacy signal: {event_type}.",
            consent_present=True,
        )
    ]


def _revelation_events(
    job_context: JobContext,
    text: str,
    characters: list[str],
    timestamp: str,
) -> list[RevelationEvent]:
    if not _REVELATION_RE.search(text):
        return []
    return [
        RevelationEvent(
            event_id=_event_id("reader_info"),
            book_id=job_context.book_id,
            scene_id=job_context.scene_id,
            fact_id=f"{job_context.scene_id}-revelation",
            timestamp=timestamp,
            revelation_type="revelation",
            fact_description="Scene contains a deterministic revelation/realization signal.",
            known_by_reader=True,
            known_by_characters=characters[:3],
            irony_type="none",
            chapter_number=int(job_context.chapter_id),
        )
    ]


def _subplot_events(
    job_context: JobContext,
    text: str,
    timestamp: str,
) -> list[SubplotEvent]:
    events: list[SubplotEvent] = []
    if _PROFESSIONAL_RE.search(text):
        events.append(_subplot_event(job_context, timestamp, "professional", priority=3))
    if _INTIMACY_RE.search(text):
        events.append(_subplot_event(job_context, timestamp, "romantic", priority=5))
    if _FAMILY_RE.search(text):
        events.append(_subplot_event(job_context, timestamp, "family", priority=2))
    return events


def _trope_events(job_context: JobContext, text: str, timestamp: str) -> list[TropeEvent]:
    source = f"{job_context.scene_brief}\n{text}"
    if not _SECOND_CHANCE_RE.search(source):
        return []
    return [
        TropeEvent(
            event_id=_event_id("trope"),
            book_id=job_context.book_id,
            scene_id=job_context.scene_id,
            trope_id="second_chance_romance",
            trope_name="Second Chance Romance",
            genre_module="romance_module_v1",
            timestamp=timestamp,
            status="activated",
            activated_at_scene=job_context.scene_id,
            required_beats=[
                RequiredBeat(
                    beat_id="second_chance_confrontation",
                    description="Former lovers confront the old wound directly.",
                    target_chapter=max(1, int(job_context.chapter_id) + 4),
                    status="pending",
                )
            ],
        )
    ]


def _promise_events(job_context: JobContext, text: str, timestamp: str) -> list[PromiseEvent]:
    events: list[PromiseEvent] = []
    if _QUESTION_RE.search(text):
        events.append(
            PromiseEvent(
                event_id=_event_id("promise"),
                book_id=job_context.book_id,
                promise_id=f"{job_context.scene_id}-character-question",
                timestamp=timestamp,
                event_type="opened",
                promise_type="character_question",
                scene_id=job_context.scene_id,
                priority="medium",
                description="Scene opens or reinforces a character question through dialogue.",
                must_resolve_by=f"ch{int(job_context.chapter_id) + 6:02d}",
                acceptable_resolutions=["answered in dialogue", "resolved through action"],
            )
        )
    if _RESOLUTION_RE.search(text):
        events.append(
            PromiseEvent(
                event_id=_event_id("promise"),
                book_id=job_context.book_id,
                promise_id=f"{job_context.scene_id}-local-resolution",
                timestamp=timestamp,
                event_type="resolved",
                promise_type="emotional_debt",
                scene_id=job_context.scene_id,
                priority="low",
                description="Scene contains a deterministic resolution/decision signal.",
                resolution_note="Local scene-level emotional debt resolved or progressed.",
            )
        )
    return events


def _subplot_event(
    job_context: JobContext,
    timestamp: str,
    subplot_type: str,
    *,
    priority: int,
) -> SubplotEvent:
    chapter = int(job_context.chapter_id)
    status = "resolved" if chapter >= 23 else "progressed" if chapter > 4 else "opened"
    return SubplotEvent(
        event_id=_event_id("subplot"),
        book_id=job_context.book_id,
        scene_id=job_context.scene_id,
        subplot_id=f"{subplot_type}_subplot",
        timestamp=timestamp,
        subplot_type=subplot_type,
        status=status,
        description=f"Deterministic {subplot_type} subplot signal.",
        priority=priority,
        opened_at_scene=job_context.scene_id if status == "opened" else None,
        target_resolution_scene="ch25_sc02" if status != "resolved" else None,
        resolution_scene=job_context.scene_id if status == "resolved" else None,
    )


def _detect_characters(text: str, character_metrics: Mapping[str, Any]) -> list[str]:
    metric_names = [str(name).lower() for name in character_metrics if str(name).strip()]
    if metric_names:
        return sorted(set(metric_names))[:4]
    counts: dict[str, int] = {}
    for match in _NAME_RE.finditer(text):
        name = match.group(0)
        if name in _EXCLUDE_NAMES:
            continue
        counts[name.lower()] = counts.get(name.lower(), 0) + 1
    return [
        name for name, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:4]
    ]


def _arc_phase(chapter: int) -> str:
    if chapter <= 3:
        return "opening"
    if chapter <= 8:
        return "wound_open"
    if chapter <= 16:
        return "processing"
    if chapter <= 22:
        return "wound_healing"
    return "resolved"


def _intimacy_type(text: str, chapter: int) -> str:
    if re.search(r"\bkiss(?:ed)?\b", text, re.IGNORECASE):
        return "first_kiss" if chapter <= 12 else "reconciliation"
    if re.search(r"\b(desire|heat|mouth|skin)\b", text, re.IGNORECASE):
        return "first_charged_moment"
    return "first_touch"


def _heat_label(heat_level: int) -> str:
    if heat_level >= 5:
        return "erotic"
    if heat_level >= 4:
        return "steamy"
    if heat_level >= 3:
        return "sensual"
    return "sweet"


def _event_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
