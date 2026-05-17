"""SeriesArcTracker — fatal-on-failure cross-book arc tracking."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pipeline.ledgers.series_promise_ledger import SeriesPromiseEvent, SeriesPromiseLedger

logger = logging.getLogger(__name__)


class SeriesArcUpdateError(RuntimeError):
    """Raised when a series arc update cannot be persisted."""


class SeriesArcTracker:
    """Records and queries cross-book arc state.

    All write operations are fatal on failure — an unrecorded arc update
    breaks series-level continuity guarantees, so we surface errors rather
    than silently swallowing them.
    """

    def __init__(self, series_promise_ledger: SeriesPromiseLedger) -> None:
        self._ledger = series_promise_ledger

    def open_thread(
        self,
        series_id: str,
        book_id: str,
        scene_id: str,
        promise_id: str,
        promise_type: str,
        description: str,
        book_number: int,
        must_resolve_by_book: int | None = None,
        cross_book_arc_id: str | None = None,
    ) -> None:
        """Record the opening of a new series-level thread. Fatal on failure."""
        event = SeriesPromiseEvent(
            event_id=str(uuid.uuid4())[:8],
            series_id=series_id,
            book_id=book_id,
            scene_id=scene_id,
            promise_id=promise_id,
            timestamp=datetime.now(UTC).isoformat(),
            promise_type=promise_type,
            status="opened",
            description=description,
            book_number=book_number,
            cross_book_arc_id=cross_book_arc_id,
            opened_book=book_number,
            must_resolve_by_book=must_resolve_by_book,
        )
        try:
            self._ledger.append(event)
            logger.info(
                "SeriesArcTracker: opened thread %s (book=%d, must_resolve_by=%s)",
                promise_id,
                book_number,
                must_resolve_by_book,
            )
        except Exception as exc:
            raise SeriesArcUpdateError(
                f"Failed to open series thread '{promise_id}': {exc}"
            ) from exc

    def progress_thread(
        self,
        series_id: str,
        book_id: str,
        scene_id: str,
        promise_id: str,
        description: str,
        book_number: int,
    ) -> None:
        """Record a progression event for an existing thread. Fatal on failure."""
        event = SeriesPromiseEvent(
            event_id=str(uuid.uuid4())[:8],
            series_id=series_id,
            book_id=book_id,
            scene_id=scene_id,
            promise_id=promise_id,
            timestamp=datetime.now(UTC).isoformat(),
            promise_type="series_thread",
            status="progressed",
            description=description,
            book_number=book_number,
        )
        try:
            self._ledger.append(event)
            logger.info("SeriesArcTracker: progressed thread %s (book=%d)", promise_id, book_number)
        except Exception as exc:
            raise SeriesArcUpdateError(
                f"Failed to progress series thread '{promise_id}': {exc}"
            ) from exc

    def resolve_thread(
        self,
        series_id: str,
        book_id: str,
        scene_id: str,
        promise_id: str,
        description: str,
        book_number: int,
    ) -> None:
        """Record resolution of a series thread. Fatal on failure."""
        event = SeriesPromiseEvent(
            event_id=str(uuid.uuid4())[:8],
            series_id=series_id,
            book_id=book_id,
            scene_id=scene_id,
            promise_id=promise_id,
            timestamp=datetime.now(UTC).isoformat(),
            promise_type="series_thread",
            status="resolved",
            description=description,
            book_number=book_number,
        )
        try:
            self._ledger.append(event)
            logger.info("SeriesArcTracker: resolved thread %s (book=%d)", promise_id, book_number)
        except Exception as exc:
            raise SeriesArcUpdateError(
                f"Failed to resolve series thread '{promise_id}': {exc}"
            ) from exc

    def get_open_threads(self, book: int) -> list[dict[str, Any]]:
        """Return all open series threads as of the given book number."""
        return [p for p in self._ledger.open_promises() if p.get("book_number", 0) <= book]

    def overdue_threads(self, current_book: int) -> list[dict[str, Any]]:
        """Return threads whose must_resolve_by_book is before current_book and still open."""
        overdue = []
        for p in self._ledger.open_promises():
            deadline = p.get("must_resolve_by_book")
            if deadline is not None and int(deadline) < current_book:
                overdue.append(p)
        return overdue
