"""SeriesArcTracker — fatal-on-failure cross-book arc tracking."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pipeline.ledgers.series_promise_ledger import SeriesPromiseEvent, SeriesPromiseLedger

if TYPE_CHECKING:
    from pipeline.core.job_context import JobContext

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
        current = self._require_open_thread(promise_id)
        event = SeriesPromiseEvent(
            event_id=str(uuid.uuid4())[:8],
            series_id=series_id,
            book_id=book_id,
            scene_id=scene_id,
            promise_id=promise_id,
            timestamp=datetime.now(UTC).isoformat(),
            promise_type=str(current.get("promise_type", "series_thread")),
            status="progressed",
            description=description,
            book_number=book_number,
            cross_book_arc_id=current.get("cross_book_arc_id"),
            opened_book=current.get("opened_book"),
            must_resolve_by_book=current.get("must_resolve_by_book"),
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
        current = self._require_open_thread(promise_id)
        event = SeriesPromiseEvent(
            event_id=str(uuid.uuid4())[:8],
            series_id=series_id,
            book_id=book_id,
            scene_id=scene_id,
            promise_id=promise_id,
            timestamp=datetime.now(UTC).isoformat(),
            promise_type=str(current.get("promise_type", "series_thread")),
            status="resolved",
            description=description,
            book_number=book_number,
            cross_book_arc_id=current.get("cross_book_arc_id"),
            opened_book=current.get("opened_book"),
            must_resolve_by_book=current.get("must_resolve_by_book"),
        )
        try:
            self._ledger.append(event)
            logger.info("SeriesArcTracker: resolved thread %s (book=%d)", promise_id, book_number)
        except Exception as exc:
            raise SeriesArcUpdateError(
                f"Failed to resolve series thread '{promise_id}': {exc}"
            ) from exc

    def apply_approved_updates(self, job_context: JobContext) -> None:
        """Apply scene-emitted series arc updates after convergence GO."""
        for raw in _extract_series_arc_updates(job_context.output_data):
            action = str(raw.get("action", raw.get("operation", raw.get("status", "")))).lower()
            promise_id = _require_str(raw, "promise_id")
            description = str(raw.get("description", ""))
            book_number = _require_int(raw, "book_number")

            if action in {"open", "opened"}:
                self.open_thread(
                    series_id=str(raw.get("series_id", job_context.series_id)),
                    book_id=str(raw.get("book_id", job_context.book_id)),
                    scene_id=str(raw.get("scene_id", job_context.scene_id)),
                    promise_id=promise_id,
                    promise_type=str(raw.get("promise_type", "series_thread")),
                    description=description,
                    book_number=book_number,
                    must_resolve_by_book=_optional_int(raw.get("must_resolve_by_book")),
                    cross_book_arc_id=_optional_str(raw.get("cross_book_arc_id")),
                )
                continue

            if action in {"progress", "progressed"}:
                self.progress_thread(
                    series_id=str(raw.get("series_id", job_context.series_id)),
                    book_id=str(raw.get("book_id", job_context.book_id)),
                    scene_id=str(raw.get("scene_id", job_context.scene_id)),
                    promise_id=promise_id,
                    description=description,
                    book_number=book_number,
                )
                continue

            if action in {"resolve", "resolved"}:
                self.resolve_thread(
                    series_id=str(raw.get("series_id", job_context.series_id)),
                    book_id=str(raw.get("book_id", job_context.book_id)),
                    scene_id=str(raw.get("scene_id", job_context.scene_id)),
                    promise_id=promise_id,
                    description=description,
                    book_number=book_number,
                )
                continue

            raise SeriesArcUpdateError(f"Unknown series arc update action '{action}'.")

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

    def _find_latest_thread(self, promise_id: str) -> dict[str, Any]:
        for payload in self._ledger.open_promises():
            if payload.get("promise_id") == promise_id:
                return payload
        return {}

    def _require_open_thread(self, promise_id: str) -> dict[str, Any]:
        payload = self._find_latest_thread(promise_id)
        if not payload:
            raise SeriesArcUpdateError(f"No open series thread found for '{promise_id}'.")
        return payload


def _extract_series_arc_updates(output_data: dict[str, Any]) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    raw_top_level = output_data.get("series_arc_updates", [])
    if isinstance(raw_top_level, list):
        updates.extend([u for u in raw_top_level if isinstance(u, dict)])

    for agent_output in output_data.values():
        if not isinstance(agent_output, dict):
            continue
        raw_nested = agent_output.get("series_arc_updates", [])
        if isinstance(raw_nested, list):
            updates.extend([u for u in raw_nested if isinstance(u, dict)])
    return updates


def _require_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if value is None or str(value) == "":
        raise SeriesArcUpdateError(f"series_arc_update missing required field '{key}'.")
    return str(value)


def _require_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if value is None:
        raise SeriesArcUpdateError(f"series_arc_update missing required field '{key}'.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SeriesArcUpdateError(f"series_arc_update field '{key}' must be an integer.") from exc


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise SeriesArcUpdateError("must_resolve_by_book must be an integer.")
    try:
        return int(value)
    except ValueError as exc:
        raise SeriesArcUpdateError("must_resolve_by_book must be an integer.") from exc


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
