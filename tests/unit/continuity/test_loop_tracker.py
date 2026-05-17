"""Unit tests for LoopTracker (Task 009)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pipeline.continuity.loop_tracker import LoopTracker
from pipeline.ledgers.promise_ledger import PromiseLedger
from pipeline.ledgers.series_promise_ledger import SeriesPromiseLedger


def _make_tracker(tmp_path: Path) -> tuple[LoopTracker, PromiseLedger, SeriesPromiseLedger]:
    promise_ledger = PromiseLedger(book_id="book1", data_root=tmp_path / "data")
    series_ledger = SeriesPromiseLedger(series_id="series1", data_root=tmp_path / "data")
    tracker = LoopTracker(promise_ledger=promise_ledger, series_promise_ledger=series_ledger)
    return tracker, promise_ledger, series_ledger


class TestEnforcePromiseDeadlines:
    def test_no_promises_returns_empty(self, tmp_path: Path) -> None:
        tracker, _, _ = _make_tracker(tmp_path)
        result = tracker.enforce_promise_deadlines(chapter=5)
        assert result == []

    def test_overdue_open_promise_detected(self, tmp_path: Path) -> None:
        tracker, _, _ = _make_tracker(tmp_path)
        # Inject a payload directly via internal patching
        with patch.object(
            tracker._promise,
            "_all_payloads",
            return_value=[
                {
                    "promise_id": "p001",
                    "must_resolve_by": "3",
                    "resolution_state": "open",
                    "description": "The chekhov gun",
                }
            ],
        ):
            result = tracker.enforce_promise_deadlines(chapter=5)
        assert len(result) == 1
        assert result[0].promise_id == "p001"
        assert result[0].deadline_chapter == 3
        assert result[0].current_chapter == 5

    def test_resolved_promise_not_overdue(self, tmp_path: Path) -> None:
        tracker, _, _ = _make_tracker(tmp_path)
        with patch.object(
            tracker._promise,
            "_all_payloads",
            return_value=[
                {
                    "promise_id": "p002",
                    "must_resolve_by": "3",
                    "resolution_state": "resolved",
                    "description": "Already resolved",
                }
            ],
        ):
            result = tracker.enforce_promise_deadlines(chapter=5)
        assert result == []

    def test_deadline_exactly_at_chapter_not_overdue(self, tmp_path: Path) -> None:
        """Deadline = chapter means the deadline is this chapter, not past it."""
        tracker, _, _ = _make_tracker(tmp_path)
        with patch.object(
            tracker._promise,
            "_all_payloads",
            return_value=[
                {
                    "promise_id": "p003",
                    "must_resolve_by": "5",
                    "resolution_state": "open",
                    "description": "Due this chapter",
                }
            ],
        ):
            result = tracker.enforce_promise_deadlines(chapter=5)
        assert result == []  # deadline < chapter required to be overdue


class TestCheckChapterCanShip:
    def test_can_ship_with_no_overdue(self, tmp_path: Path) -> None:
        tracker, _, _ = _make_tracker(tmp_path)
        assert tracker.check_chapter_can_ship(chapter=10) is True

    def test_cannot_ship_with_overdue(self, tmp_path: Path) -> None:
        tracker, _, _ = _make_tracker(tmp_path)
        with patch.object(
            tracker._promise,
            "_all_payloads",
            return_value=[
                {
                    "promise_id": "p004",
                    "must_resolve_by": "8",
                    "resolution_state": "open",
                    "description": "Must resolve",
                }
            ],
        ):
            assert tracker.check_chapter_can_ship(chapter=10) is False


class TestEnforceSeriesThreads:
    def test_no_series_promises_returns_empty(self, tmp_path: Path) -> None:
        tracker, _, _ = _make_tracker(tmp_path)
        result = tracker.enforce_series_threads(book=3)
        assert result == []

    def test_overdue_series_thread_detected(self, tmp_path: Path) -> None:
        tracker, _, _ = _make_tracker(tmp_path)
        with patch.object(
            tracker._series_promise,
            "_all_payloads",
            return_value=[
                {
                    "promise_id": "sp001",
                    "must_resolve_by_book": "2",
                    "resolution_state": "open",
                    "description": "Series arc",
                }
            ],
        ):
            result = tracker.enforce_series_threads(book=3)
        assert len(result) == 1
        assert result[0].promise_id == "sp001"
        assert result[0].deadline_book == 2
        assert result[0].current_book == 3
