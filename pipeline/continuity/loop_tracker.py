"""LoopTracker — promise deadline enforcement for scene shipment gating."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pipeline.ledgers.promise_ledger import PromiseLedger
from pipeline.ledgers.series_promise_ledger import SeriesPromiseLedger

logger = logging.getLogger(__name__)


@dataclass
class OverduePromise:
    promise_id: str
    deadline_chapter: int
    current_chapter: int
    description: str = ""


@dataclass
class OverdueSeriesPromise:
    promise_id: str
    deadline_book: int
    current_book: int
    description: str = ""


class LoopTracker:
    """Enforces promise deadlines before allowing a chapter to ship."""

    def __init__(
        self,
        promise_ledger: PromiseLedger,
        series_promise_ledger: SeriesPromiseLedger,
    ) -> None:
        self._promise = promise_ledger
        self._series_promise = series_promise_ledger

    def enforce_promise_deadlines(self, chapter: int) -> list[OverduePromise]:
        """Return all promises that are overdue by chapter ``chapter``."""
        overdue: list[OverduePromise] = []
        all_payloads = self._promise._all_payloads()
        for payload in all_payloads:
            deadline = payload.get("must_resolve_by")
            resolution_state = payload.get("resolution_state", "open")
            if deadline is not None and int(deadline) < chapter and resolution_state == "open":
                overdue.append(
                    OverduePromise(
                        promise_id=str(payload.get("promise_id", "")),
                        deadline_chapter=int(deadline),
                        current_chapter=chapter,
                        description=str(payload.get("description", "")),
                    )
                )
        return overdue

    def check_chapter_can_ship(self, chapter: int) -> bool:
        """Return False if any overdue promises exist for this chapter."""
        return len(self.enforce_promise_deadlines(chapter)) == 0

    def enforce_series_threads(self, book: int) -> list[OverdueSeriesPromise]:
        """Return all series promises overdue by book ``book``."""
        overdue: list[OverdueSeriesPromise] = []
        all_payloads = self._series_promise._all_payloads()
        for payload in all_payloads:
            deadline = payload.get("must_resolve_by_book")
            resolution_state = payload.get("resolution_state", "open")
            if deadline is not None and int(deadline) < book and resolution_state == "open":
                overdue.append(
                    OverdueSeriesPromise(
                        promise_id=str(payload.get("promise_id", "")),
                        deadline_book=int(deadline),
                        current_book=book,
                        description=str(payload.get("description", "")),
                    )
                )
        return overdue

    def mark_promise_resolved(self, promise_id: str, resolution_scene: str) -> None:
        """Mark a promise as resolved (appends a resolution event to ledger)."""
        import uuid
        from datetime import UTC, datetime

        from pipeline.ledgers.promise_ledger import PromiseEvent

        event = PromiseEvent(
            event_id=str(uuid.uuid4())[:8],
            book_id="",
            promise_id=promise_id,
            timestamp=datetime.now(UTC).isoformat(),
            event_type="resolved",
            promise_type="narrative_promise",
            scene_id=resolution_scene,
            priority="medium",
            description=f"Resolved at scene {resolution_scene}",
            resolution_note=resolution_scene,
        )
        self._promise.append(event)
        logger.info("LoopTracker: resolved promise %s at scene %s", promise_id, resolution_scene)
