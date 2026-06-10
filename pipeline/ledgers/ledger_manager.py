"""LedgerManager — aggregates all 10 ledgers for a single book run.

Injected into every agent's AgentContext in Phase 6. Keeps the per-book
ledger instances alive for the duration of a pipeline run. The
get_dashboard_summary() output is injected into every scene's context pack;
it is deliberately compact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.ledgers.bible_tracker import BibleTracker
from pipeline.ledgers.book_metrics_ledger import BookMetricsEvent, BookMetricsLedger
from pipeline.ledgers.character_arc_ledger import CharacterArcLedger
from pipeline.ledgers.intimacy_escalation_ledger import IntimacyEscalationLedger
from pipeline.ledgers.promise_ledger import PromiseLedger
from pipeline.ledgers.reader_information_state_ledger import ReaderInformationStateLedger
from pipeline.ledgers.scene_rhythm_ledger import SceneRhythmEntry, SceneRhythmLedger
from pipeline.ledgers.series_promise_ledger import SeriesPromiseLedger
from pipeline.ledgers.subplot_ledger import SubplotLedger
from pipeline.ledgers.trope_commitment_ledger import TropeCommitmentLedger


@dataclass
class SceneResult:
    """Minimal typed container the pipeline emits after a scene is finalized."""

    scene_id: str
    book_id: str
    chapter_id: str
    timestamp: str
    scene_type: str  # action/dialogue/introspection/transition/sex/aftermath/setup
    metrics_event: BookMetricsEvent | None = None
    character_arc_events: list[Any] = field(default_factory=list)
    intimacy_events: list[Any] = field(default_factory=list)
    revelation_events: list[Any] = field(default_factory=list)
    subplot_events: list[Any] = field(default_factory=list)
    trope_events: list[Any] = field(default_factory=list)
    promise_events: list[Any] = field(default_factory=list)
    continuity_events: list[Any] = field(default_factory=list)


@dataclass
class AuthorDashboard:
    """Compact snapshot of all 10 ledger states. Injected into context packs."""

    book_id: str
    scene_id: str
    # BookMetrics
    word_count_total: int = 0
    interiority_pct_running: float = 0.0
    dialogue_ratio_running: float = 0.0
    ai_tell_count_total: int = 0
    sex_scene_count: int = 0
    # Character arcs: char_id → arc_phase
    character_arcs: dict[str, str | None] = field(default_factory=dict)
    # Intimacy: pair_id → last_act_type
    intimacy_pairs: dict[str, str | None] = field(default_factory=dict)
    # Reader information state
    reader_info_known: int = 0
    reader_info_unknown: int = 0
    reader_info_active_irony: int = 0
    # Subplot
    subplots_open: int = 0
    subplots_resolved: int = 0
    # Trope
    trope_beats_pending: int = 0
    trope_beats_overdue: int = 0
    # Series promises
    series_promises_open: int = 0
    # Scene rhythm (last 10 types)
    scene_rhythm: list[str] = field(default_factory=list)
    # Promise ledger
    promises_open: int = 0
    promises_critical_open: int = 0
    # Bible/continuity
    bible_unresolved_contradictions: int = 0


class LedgerManager:
    """Opens/creates all 10 ledger instances for a given book_id."""

    def __init__(
        self,
        book_id: str,
        series_id: str | None = None,
        data_root: Path = Path("data"),
    ) -> None:
        self.book_id = book_id
        self.series_id = series_id or book_id
        self.data_root = data_root

        self.book_metrics = BookMetricsLedger(book_id, data_root)
        self.character_arc = CharacterArcLedger(book_id, data_root)
        self.intimacy = IntimacyEscalationLedger(book_id, data_root)
        self.reader_info = ReaderInformationStateLedger(book_id, data_root)
        self.subplot = SubplotLedger(book_id, data_root)
        self.trope = TropeCommitmentLedger(book_id, data_root)
        self.series_promise = SeriesPromiseLedger(self.series_id, data_root)
        self.promise = PromiseLedger(book_id, data_root)
        self.bible = BibleTracker(book_id, data_root)
        self.scene_rhythm = SceneRhythmLedger(window=10)

    def update(self, scene_result: SceneResult) -> None:
        """Dispatch scene data to every ledger that has new events."""
        if scene_result.metrics_event is not None:
            self.book_metrics.append(scene_result.metrics_event)

        for e in scene_result.character_arc_events:
            self.character_arc.append(e)

        for e in scene_result.intimacy_events:
            self.intimacy.append(e)

        for e in scene_result.revelation_events:
            self.reader_info.append(e)

        for e in scene_result.subplot_events:
            self.subplot.append(e)

        for e in scene_result.trope_events:
            self.trope.append(e)

        for e in scene_result.promise_events:
            self.promise.append(e)

        for e in scene_result.continuity_events:
            self.bible.append(e)

        self.scene_rhythm.append(
            SceneRhythmEntry(
                scene_id=scene_result.scene_id,
                scene_type=scene_result.scene_type,
            )
        )

    def get_dashboard_summary(self, book_id: str, scene_id: str) -> AuthorDashboard:
        """Collect running state from all 10 ledgers into a compact AuthorDashboard."""
        totals = self.book_metrics.compute_running_totals()
        reader_summary = self.reader_info.summary()
        subplot_summary = self.subplot.summary()
        trope_summary = self.trope.summary()
        series_summary = self.series_promise.summary()
        promise_summary = self.promise.summary()
        bible_summary = self.bible.summary()

        # Collect known character IDs from arc events
        arc_events = self.character_arc._all_payloads()
        char_ids: set[str] = {e["character_id"] for e in arc_events}
        character_arcs = {cid: self.character_arc.get_arc_position(cid) for cid in char_ids}

        # Collect known pair IDs from intimacy events
        intimacy_events = self.intimacy._all_payloads()
        pair_ids: set[str] = {e["pair_id"] for e in intimacy_events}
        intimacy_pairs = {pid: self.intimacy.last_act_type(pid) for pid in pair_ids}

        return AuthorDashboard(
            book_id=book_id,
            scene_id=scene_id,
            word_count_total=totals.word_count_total,
            interiority_pct_running=totals.interiority_pct_running,
            dialogue_ratio_running=totals.dialogue_ratio_running,
            ai_tell_count_total=totals.ai_tell_count_total,
            sex_scene_count=totals.sex_scene_count,
            character_arcs=character_arcs,
            intimacy_pairs=intimacy_pairs,
            reader_info_known=reader_summary["known_by_reader"],
            reader_info_unknown=reader_summary["unknown_by_reader"],
            reader_info_active_irony=reader_summary["active_irony"],
            subplots_open=subplot_summary["open"],
            subplots_resolved=subplot_summary["resolved"],
            trope_beats_pending=trope_summary["pending"],
            trope_beats_overdue=trope_summary["overdue"],
            series_promises_open=series_summary["open"],
            scene_rhythm=self.scene_rhythm.recent_types(),
            promises_open=promise_summary["open"],
            promises_critical_open=promise_summary["critical_open"],
            bible_unresolved_contradictions=bible_summary["unresolved_contradictions"],
        )

    def get_metrics_history(
        self,
        granularity: str = "chapter",
        metric: str | None = None,
    ) -> dict[str, Any]:
        """Return dashboard metrics history from the BookMetricsLedger."""
        return {
            "book_id": self.book_id,
            "granularity": granularity,
            "metric": metric,
            "items": self.book_metrics.metrics_history(granularity=granularity, metric=metric),
        }

    def get_character_metrics(self, character_id: str) -> dict[str, Any]:
        """Return per-scene metrics for one character from the BookMetricsLedger."""
        return {
            "book_id": self.book_id,
            "character_id": character_id,
            "items": self.book_metrics.character_metrics_history(character_id),
        }

    def close(self) -> None:
        for ledger in [
            self.book_metrics,
            self.character_arc,
            self.intimacy,
            self.reader_info,
            self.subplot,
            self.trope,
            self.series_promise,
            self.promise,
            self.bible,
        ]:
            ledger.close()
