"""Ledger system tests — append-only enforcement, running totals, quality evaluator."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pipeline.ledgers.base import LedgerError
from pipeline.ledgers.book_metrics_ledger import BookMetricsEvent, BookMetricsLedger
from pipeline.ledgers.character_arc_ledger import CharacterArcEvent, CharacterArcLedger
from pipeline.ledgers.intimacy_escalation_ledger import IntimacyEscalationLedger, IntimacyEvent
from pipeline.ledgers.ledger_manager import AuthorDashboard, LedgerManager, SceneResult
from pipeline.ledgers.quality_evaluator import QualityEvaluator, Verdict

FIXTURE_PATH = (
    Path(__file__).parent.parent.parent / "fixtures" / "ledgers" / "fixture_scene_result.json"
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def tmp_book_id(tmp_path: Path) -> tuple[str, Path]:
    return _uid(), tmp_path


@pytest.fixture
def metrics_ledger(tmp_book_id: tuple[str, Path]) -> BookMetricsLedger:
    book_id, tmp = tmp_book_id
    return BookMetricsLedger(book_id, data_root=tmp)


def _make_metrics_event(
    book_id: str,
    word_count: int = 1000,
    interiority: float = 0.30,
    chapter_id: str | None = None,
    scene_id: str | None = None,
    character_metrics: dict[str, Any] | None = None,
) -> BookMetricsEvent:
    return BookMetricsEvent(
        event_id=_uid(),
        book_id=book_id,
        chapter_id=chapter_id or _uid(),
        scene_id=scene_id or _uid(),
        timestamp=_now(),
        word_count=word_count,
        interiority_pct=interiority,
        dialogue_ratio=0.40,
        exposition_pct=0.15,
        action_pct=0.10,
        sensory_density_per_1k=8.0,
        em_dash_density=3.0,
        sentence_length_avg=14.0,
        ai_tell_count=1,
        no_fly_violations=0,
        heat_curve_position=0.2,
        sex_scene_flag=False,
        character_metrics=character_metrics or {},
    )


# ── Append-only enforcement ───────────────────────────────────────────────────


class TestAppendOnly:
    def test_duplicate_event_raises(
        self, metrics_ledger: BookMetricsLedger, tmp_book_id: tuple[str, Path]
    ) -> None:
        book_id, _ = tmp_book_id
        event = _make_metrics_event(book_id)
        metrics_ledger.append(event)
        with pytest.raises(LedgerError, match="Duplicate event_id"):
            metrics_ledger.append(event)  # same event_id

    def test_different_event_ids_succeed(
        self, metrics_ledger: BookMetricsLedger, tmp_book_id: tuple[str, Path]
    ) -> None:
        book_id, _ = tmp_book_id
        e1 = _make_metrics_event(book_id)
        e2 = _make_metrics_event(book_id)
        assert e1.event_id != e2.event_id
        metrics_ledger.append(e1)
        metrics_ledger.append(e2)
        assert metrics_ledger.compute_running_totals().word_count_total == 2000

    def test_no_update_or_delete_sql(self) -> None:
        """Verify no SQL UPDATE/DELETE statements exist inside string literals in ledger modules.

        We scan for the SQL keywords inside string literals only.
        Python identifiers like ``update()`` and comments are not SQL.
        """
        import re

        ledger_dir = Path("pipeline/ledgers")
        # Match UPDATE or DELETE as SQL keywords within string literals
        # (preceded/followed by whitespace, quotes, or start of string)
        sql_pattern = re.compile(r'["\'].*?\b(UPDATE|DELETE)\b.*?["\']', re.IGNORECASE)
        violations: list[str] = []

        for py_file in ledger_dir.glob("*.py"):
            src = py_file.read_text()
            for i, line in enumerate(src.splitlines(), start=1):
                if sql_pattern.search(line):
                    violations.append(f"{py_file.name}:{i}: {line.strip()}")

        assert not violations, "Found SQL UPDATE/DELETE in string literals:\n" + "\n".join(
            violations
        )


# ── Running totals ─────────────────────────────────────────────────────────────


class TestRunningTotals:
    def test_empty_ledger_returns_zero_totals(self, metrics_ledger: BookMetricsLedger) -> None:
        totals = metrics_ledger.compute_running_totals()
        assert totals.word_count_total == 0
        assert totals.interiority_pct_running == 0.0

    def test_single_event_totals(
        self, metrics_ledger: BookMetricsLedger, tmp_book_id: tuple[str, Path]
    ) -> None:
        book_id, _ = tmp_book_id
        event = _make_metrics_event(book_id, word_count=1000, interiority=0.35)
        metrics_ledger.append(event)
        totals = metrics_ledger.compute_running_totals()
        assert totals.word_count_total == 1000
        assert abs(totals.interiority_pct_running - 0.35) < 1e-6

    def test_weighted_average_across_scenes(
        self, metrics_ledger: BookMetricsLedger, tmp_book_id: tuple[str, Path]
    ) -> None:
        book_id, _ = tmp_book_id
        # 1000 words at 0.20, 3000 words at 0.40 → weighted avg = (200 + 1200) / 4000 = 0.35
        e1 = _make_metrics_event(book_id, word_count=1000, interiority=0.20)
        e2 = _make_metrics_event(book_id, word_count=3000, interiority=0.40)
        metrics_ledger.append(e1)
        metrics_ledger.append(e2)
        totals = metrics_ledger.compute_running_totals()
        assert totals.word_count_total == 4000
        assert abs(totals.interiority_pct_running - 0.35) < 1e-6

    def test_budget_remaining(
        self, metrics_ledger: BookMetricsLedger, tmp_book_id: tuple[str, Path]
    ) -> None:
        book_id, _ = tmp_book_id
        metrics_ledger.append(_make_metrics_event(book_id, word_count=1000, interiority=0.20))
        budget = metrics_ledger.budget_remaining(
            targets={"interiority_pct": 0.30}, word_count_remaining=5000
        )
        # current=0.20, target=0.30 → headroom=(0.30-0.20)*5000=500
        assert abs(budget["interiority_pct"] - 500.0) < 1.0


# ── Metrics history ────────────────────────────────────────────────────────────


class TestMetricsHistory:
    def test_scene_metric_history_supports_metric_filter(
        self, metrics_ledger: BookMetricsLedger, tmp_book_id: tuple[str, Path]
    ) -> None:
        book_id, _ = tmp_book_id
        metrics_ledger.append(
            _make_metrics_event(
                book_id,
                chapter_id="chapter-01",
                scene_id="scene-01",
                interiority=0.25,
            )
        )

        rows = metrics_ledger.metrics_history(granularity="scene", metric="interiority_pct")

        assert rows == [
            {
                "event_id": rows[0]["event_id"],
                "book_id": book_id,
                "chapter_id": "chapter-01",
                "scene_id": "scene-01",
                "timestamp": rows[0]["timestamp"],
                "word_count": 1000,
                "metrics": {"interiority_pct": 0.25},
            }
        ]

    def test_chapter_metric_history_aggregates_weighted_values(
        self, metrics_ledger: BookMetricsLedger, tmp_book_id: tuple[str, Path]
    ) -> None:
        book_id, _ = tmp_book_id
        metrics_ledger.append(
            _make_metrics_event(
                book_id,
                word_count=1000,
                interiority=0.20,
                chapter_id="chapter-01",
                scene_id="scene-01",
            )
        )
        metrics_ledger.append(
            _make_metrics_event(
                book_id,
                word_count=3000,
                interiority=0.40,
                chapter_id="chapter-01",
                scene_id="scene-02",
            )
        )

        rows = metrics_ledger.metrics_history(granularity="chapter")

        assert len(rows) == 1
        assert rows[0]["chapter_id"] == "chapter-01"
        assert rows[0]["scene_count"] == 2
        assert rows[0]["word_count"] == 4000
        assert abs(rows[0]["metrics"]["interiority_pct"] - 0.35) < 1e-6
        assert rows[0]["metrics"]["ai_tell_count"] == 2

    def test_character_metrics_history_filters_by_character(
        self, metrics_ledger: BookMetricsLedger, tmp_book_id: tuple[str, Path]
    ) -> None:
        book_id, _ = tmp_book_id
        metrics_ledger.append(
            _make_metrics_event(
                book_id,
                chapter_id="chapter-01",
                scene_id="scene-01",
                character_metrics={"sarah": {"mtld": 72.5}, "miles": {"mtld": 60.0}},
            )
        )

        rows = metrics_ledger.character_metrics_history("sarah")

        assert len(rows) == 1
        assert rows[0]["chapter_id"] == "chapter-01"
        assert rows[0]["scene_id"] == "scene-01"
        assert rows[0]["metrics"] == {"mtld": 72.5}

    def test_invalid_metric_filter_raises_value_error(
        self, metrics_ledger: BookMetricsLedger
    ) -> None:
        with pytest.raises(ValueError, match="Unsupported metric"):
            metrics_ledger.metrics_history(granularity="scene", metric="unknown_metric")


# ── QualityEvaluator ───────────────────────────────────────────────────────────


class TestQualityEvaluator:
    def setup_method(self) -> None:
        self.evaluator = QualityEvaluator()

    def _running(self, interiority: float, total_words: int = 40000) -> dict[str, float]:
        return {"interiority_pct": interiority, "word_count_total": float(total_words)}

    def _scene(self, interiority: float, words: int = 1200) -> dict[str, float]:
        return {"interiority_pct": interiority, "word_count": float(words)}

    def test_high_interiority_passes_when_below_target(self) -> None:
        """High-interiority scene should be POSITIVE when running total is below target."""
        decision = self.evaluator.evaluate_scene_contribution(
            scene_metrics=self._scene(interiority=0.50),
            running_totals=self._running(interiority=0.20),
            targets={"interiority_pct": 0.35},
            word_count_remaining=80000,
        )
        assert decision.overall_verdict in {Verdict.POSITIVE, Verdict.NEUTRAL}
        m = next(r for r in decision.metric_results if r.metric == "interiority_pct")
        assert m.projected_running > m.current_running

    def test_high_interiority_negative_when_at_target(self) -> None:
        """High-interiority scene should be NEGATIVE when running total is at/above target."""
        decision = self.evaluator.evaluate_scene_contribution(
            scene_metrics=self._scene(interiority=0.60),
            running_totals=self._running(interiority=0.35),
            targets={"interiority_pct": 0.35},
            word_count_remaining=20000,
        )
        m = next(r for r in decision.metric_results if r.metric == "interiority_pct")
        assert m.verdict == Verdict.NEGATIVE

    def test_exception_returns_needs_review(self) -> None:
        """Any evaluator exception must yield needs_review — fail-closed."""
        decision = self.evaluator.evaluate_scene_contribution(
            scene_metrics={"word_count": "not_a_number"},  # type: ignore[dict-item]
            running_totals={},
            targets={"interiority_pct": 0.35},
            word_count_remaining=10000,
        )
        assert decision.overall_verdict == Verdict.NEEDS_REVIEW

    def test_empty_targets_yields_neutral(self) -> None:
        decision = self.evaluator.evaluate_scene_contribution(
            scene_metrics=self._scene(interiority=0.40),
            running_totals=self._running(interiority=0.30),
            targets={},
            word_count_remaining=10000,
        )
        assert decision.overall_verdict == Verdict.NEUTRAL
        assert decision.metric_results == []


# ── LedgerManager fixture test ─────────────────────────────────────────────────


class TestLedgerManager:
    def _make_scene_result(self, book_id: str) -> SceneResult:
        fixture = json.loads(FIXTURE_PATH.read_text())
        m = fixture["metrics"]
        metrics_event = BookMetricsEvent(
            event_id=_uid(),
            book_id=book_id,
            chapter_id=_uid(),
            scene_id=_uid(),
            timestamp=_now(),
            word_count=m["word_count"],
            interiority_pct=m["interiority_pct"],
            dialogue_ratio=m["dialogue_ratio"],
            exposition_pct=m["exposition_pct"],
            action_pct=m["action_pct"],
            sensory_density_per_1k=m["sensory_density_per_1k"],
            em_dash_density=m["em_dash_density"],
            sentence_length_avg=m["sentence_length_avg"],
            ai_tell_count=m["ai_tell_count"],
            no_fly_violations=m["no_fly_violations"],
            heat_curve_position=m["heat_curve_position"],
            sex_scene_flag=m["sex_scene_flag"],
        )
        # Build character arc events
        arc_events = []
        for ae in fixture.get("character_arc_events", []):
            arc_events.append(
                CharacterArcEvent(
                    event_id=_uid(),
                    book_id=book_id,
                    scene_id=_uid(),
                    character_id=ae["character_id"],
                    timestamp=_now(),
                    arc_phase=ae["arc_phase"],
                    wound_state=ae["wound_state"],
                    belief_current=ae["belief_current"],
                    belief_true=ae["belief_true"],
                )
            )
        return SceneResult(
            scene_id=_uid(),
            book_id=book_id,
            chapter_id=_uid(),
            timestamp=_now(),
            scene_type=fixture["scene_type"],
            metrics_event=metrics_event,
            character_arc_events=arc_events,
        )

    def test_fixture_scene_updates_all_ledgers(self, tmp_path: Path) -> None:
        book_id = _uid()
        manager = LedgerManager(book_id=book_id, data_root=tmp_path)
        scene = self._make_scene_result(book_id)
        manager.update(scene)

        dashboard = manager.get_dashboard_summary(book_id, scene.scene_id)

        assert isinstance(dashboard, AuthorDashboard)
        assert dashboard.word_count_total == 1200
        assert len(dashboard.character_arcs) >= 1
        assert dashboard.scene_rhythm == ["dialogue"]
        manager.close()

    def test_dashboard_has_all_10_states_populated(self, tmp_path: Path) -> None:
        """After a scene update every dashboard field is present (even if zero)."""
        book_id = _uid()
        manager = LedgerManager(book_id=book_id, data_root=tmp_path)
        scene = self._make_scene_result(book_id)
        manager.update(scene)
        dashboard = manager.get_dashboard_summary(book_id, scene.scene_id)

        # All fields must exist and have correct types
        assert isinstance(dashboard.word_count_total, int)
        assert isinstance(dashboard.character_arcs, dict)
        assert isinstance(dashboard.intimacy_pairs, dict)
        assert isinstance(dashboard.reader_info_known, int)
        assert isinstance(dashboard.subplots_open, int)
        assert isinstance(dashboard.trope_beats_pending, int)
        assert isinstance(dashboard.series_promises_open, int)
        assert isinstance(dashboard.scene_rhythm, list)
        assert isinstance(dashboard.promises_open, int)
        assert isinstance(dashboard.bible_unresolved_contradictions, int)
        manager.close()

    def test_metrics_query_methods_wrap_book_metrics_ledger(self, tmp_path: Path) -> None:
        book_id = _uid()
        manager = LedgerManager(book_id=book_id, data_root=tmp_path)
        scene_id = "scene-01"
        scene = SceneResult(
            scene_id=scene_id,
            book_id=book_id,
            chapter_id="chapter-01",
            timestamp=_now(),
            scene_type="dialogue",
            metrics_event=_make_metrics_event(
                book_id,
                chapter_id="chapter-01",
                scene_id=scene_id,
                character_metrics={"sarah": {"mtld": 72.5}},
            ),
        )
        manager.update(scene)

        history = manager.get_metrics_history(granularity="scene", metric="interiority_pct")
        character_history = manager.get_character_metrics("sarah")

        assert history["book_id"] == book_id
        assert history["items"][0]["scene_id"] == scene_id
        assert history["items"][0]["metrics"] == {"interiority_pct": 0.30}
        assert character_history["character_id"] == "sarah"
        assert character_history["items"][0]["metrics"] == {"mtld": 72.5}
        manager.close()


# ── CharacterArcLedger ─────────────────────────────────────────────────────────


class TestCharacterArcLedger:
    def test_get_arc_position_returns_latest(self, tmp_path: Path) -> None:
        book_id = _uid()
        ledger = CharacterArcLedger(book_id, data_root=tmp_path)
        char_id = _uid()

        def arc_event(phase: str) -> CharacterArcEvent:
            return CharacterArcEvent(
                event_id=_uid(),
                book_id=book_id,
                scene_id=_uid(),
                character_id=char_id,
                timestamp=_now(),
                arc_phase=phase,
                wound_state="test",
                belief_current="x",
                belief_true="y",
            )

        ledger.append(arc_event("opening"))
        ledger.append(arc_event("wound_open"))
        assert ledger.get_arc_position(char_id) == "wound_open"
        ledger.close()

    def test_get_arc_position_unknown_character(self, tmp_path: Path) -> None:
        book_id = _uid()
        ledger = CharacterArcLedger(book_id, data_root=tmp_path)
        assert ledger.get_arc_position(_uid()) is None
        ledger.close()


# ── IntimacyEscalationLedger ───────────────────────────────────────────────────


class TestIntimacyEscalationLedger:
    def test_validate_escalation_first_touch_accepted(self, tmp_path: Path) -> None:
        book_id = _uid()
        ledger = IntimacyEscalationLedger(book_id, data_root=tmp_path)
        pair_id = _uid()
        assert ledger.validate_escalation(pair_id, "first_touch") is True
        ledger.close()

    def test_validate_escalation_skip_rejected(self, tmp_path: Path) -> None:
        """Can't jump straight to first_explicit after first_touch."""
        book_id = _uid()
        pair_id = _uid()
        ledger = IntimacyEscalationLedger(book_id, data_root=tmp_path)

        def intimacy_event(event_type: str) -> IntimacyEvent:
            return IntimacyEvent(
                event_id=_uid(),
                book_id=book_id,
                scene_id=_uid(),
                pair_id=pair_id,
                character_pair=["a", "b"],
                chapter_number=1,
                timestamp=_now(),
                event_type=event_type,
                heat_level="sensual",
                description="test",
            )

        ledger.append(intimacy_event("first_touch"))
        assert ledger.validate_escalation(pair_id, "first_explicit") is False
        ledger.close()

    def test_validate_escalation_sequential_accepted(self, tmp_path: Path) -> None:
        book_id = _uid()
        pair_id = _uid()
        ledger = IntimacyEscalationLedger(book_id, data_root=tmp_path)

        def ie(event_type: str) -> IntimacyEvent:
            return IntimacyEvent(
                event_id=_uid(),
                book_id=book_id,
                scene_id=_uid(),
                pair_id=pair_id,
                character_pair=["a", "b"],
                chapter_number=1,
                timestamp=_now(),
                event_type=event_type,
                heat_level="sensual",
                description="test",
            )

        ledger.append(ie("first_touch"))
        assert ledger.validate_escalation(pair_id, "first_charged_moment") is True
        ledger.close()
