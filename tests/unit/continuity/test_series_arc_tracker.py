"""Unit tests for SeriesArcTracker."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.continuity.series_arc_tracker import SeriesArcTracker, SeriesArcUpdateError
from pipeline.core.job_context import JobContext
from pipeline.ledgers.series_promise_ledger import SeriesPromiseEvent, SeriesPromiseLedger
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)


def _make_spec() -> ProjectSpec:
    return ProjectSpec(
        book_id="book1",
        series_id="series1",
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(),
        sensitivity_thresholds=ResolvedSensitivityThresholds(),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )


def _make_tracker(tmp_path: Path) -> SeriesArcTracker:
    ledger = SeriesPromiseLedger(series_id="series1", data_root=tmp_path / "data")
    return SeriesArcTracker(ledger)


def _make_job(output_data: dict[str, object]) -> JobContext:
    return JobContext(
        job_id="job1",
        series_id="series1",
        book_id="book1",
        chapter_id=1,
        scene_id="ch01_sc01",
        spec=_make_spec(),
        output_data=output_data,
    )


def test_progress_preserves_deadline_metadata(tmp_path: Path) -> None:
    tracker = _make_tracker(tmp_path)
    tracker.open_thread(
        series_id="series1",
        book_id="book1",
        scene_id="ch01_sc01",
        promise_id="sp001",
        promise_type="series_thread",
        description="Secret family thread opens.",
        book_number=1,
        must_resolve_by_book=2,
        cross_book_arc_id="arc-family",
    )

    tracker.progress_thread(
        series_id="series1",
        book_id="book2",
        scene_id="ch03_sc01",
        promise_id="sp001",
        description="Family thread escalates.",
        book_number=2,
    )

    open_threads = tracker.get_open_threads(book=2)
    assert open_threads[0]["must_resolve_by_book"] == 2
    assert open_threads[0]["cross_book_arc_id"] == "arc-family"
    assert tracker.overdue_threads(current_book=3)[0]["promise_id"] == "sp001"


def test_resolved_thread_no_longer_open(tmp_path: Path) -> None:
    tracker = _make_tracker(tmp_path)
    tracker.open_thread(
        series_id="series1",
        book_id="book1",
        scene_id="ch01_sc01",
        promise_id="sp001",
        promise_type="series_thread",
        description="Secret family thread opens.",
        book_number=1,
        must_resolve_by_book=2,
    )
    tracker.resolve_thread(
        series_id="series1",
        book_id="book2",
        scene_id="ch12_sc01",
        promise_id="sp001",
        description="Secret family thread resolves.",
        book_number=2,
    )

    assert tracker.get_open_threads(book=3) == []
    assert tracker.overdue_threads(current_book=3) == []


def test_progress_missing_thread_is_fatal(tmp_path: Path) -> None:
    tracker = _make_tracker(tmp_path)

    with pytest.raises(SeriesArcUpdateError, match="No open series thread"):
        tracker.progress_thread(
            series_id="series1",
            book_id="book2",
            scene_id="ch03_sc01",
            promise_id="missing",
            description="Missing thread progresses.",
            book_number=2,
        )


def test_apply_approved_updates_from_agent_scoped_output(tmp_path: Path) -> None:
    tracker = _make_tracker(tmp_path)
    job = _make_job(
        {
            "editor_agent": {
                "series_arc_updates": [
                    {
                        "action": "open",
                        "promise_id": "sp001",
                        "promise_type": "series_thread",
                        "description": "Secret family thread opens.",
                        "book_number": 1,
                        "must_resolve_by_book": 2,
                    }
                ]
            }
        }
    )

    tracker.apply_approved_updates(job)

    open_threads = tracker.get_open_threads(book=1)
    assert open_threads[0]["promise_id"] == "sp001"
    assert open_threads[0]["must_resolve_by_book"] == 2


def test_apply_unknown_series_arc_action_is_fatal(tmp_path: Path) -> None:
    tracker = _make_tracker(tmp_path)
    job = _make_job(
        {
            "series_arc_updates": [
                {
                    "action": "teleport",
                    "promise_id": "sp001",
                    "description": "Unknown action.",
                    "book_number": 1,
                }
            ]
        }
    )

    with pytest.raises(SeriesArcUpdateError, match="Unknown series arc update action"):
        tracker.apply_approved_updates(job)


def test_series_arc_update_failure_is_fatal_by_default() -> None:
    class FailingLedger:
        def append(self, event: SeriesPromiseEvent) -> None:
            raise RuntimeError("disk unavailable")

        def open_promises(self) -> list[dict[str, object]]:
            return []

    tracker = SeriesArcTracker(FailingLedger())  # type: ignore[arg-type]

    with pytest.raises(SeriesArcUpdateError, match="Failed to open series thread"):
        tracker.open_thread(
            series_id="series1",
            book_id="book1",
            scene_id="ch01_sc01",
            promise_id="sp001",
            promise_type="series_thread",
            description="Secret family thread opens.",
            book_number=1,
        )
