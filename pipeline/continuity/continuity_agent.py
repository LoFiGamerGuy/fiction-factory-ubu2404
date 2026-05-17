"""ContinuityAgent — checks bible consistency and promise deadlines before convergence."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from pipeline.continuity.bible_steward import BibleSteward
from pipeline.continuity.bible_types import BibleDelta, BibleState
from pipeline.continuity.loop_tracker import LoopTracker
from pipeline.core.job_context import JobContext

logger = logging.getLogger(__name__)


class ContinuityAgent:
    """Wraps BibleSteward and LoopTracker; sets bible_contradiction and overdue_promises."""

    def __init__(
        self,
        bible_steward: BibleSteward,
        loop_tracker: LoopTracker,
    ) -> None:
        self._steward = bible_steward
        self._tracker = loop_tracker

    def run(self, job_context: JobContext) -> JobContext:
        """Check continuity for the current scene and annotate JobContext.

        - Validates any bible deltas embedded in output_data["bible_deltas"]
        - Checks promise deadlines for this chapter
        - Sets bible_contradiction=True if any delta is invalid
        - Populates overdue_promises with IDs of overdue open promises
        """
        bible_contradiction = False
        overdue: list[str] = []

        # 1. Validate proposed bible deltas (if any)
        pending_deltas: list[dict[str, Any]] = job_context.output_data.get("bible_deltas", [])
        if pending_deltas:
            current_bible: BibleState = self._steward._load_state(job_context.book_id)
            for raw in pending_deltas:
                try:
                    delta = BibleDelta(
                        delta_id=str(raw.get("delta_id", "")),
                        entity_id=str(raw.get("entity_id", "")),
                        entity_type=str(raw.get("entity_type", "character")),
                        operation=str(raw.get("operation", "upsert")),
                        new_attributes=raw.get("new_attributes", {}),
                        timeline_event=raw.get("timeline_event"),
                        source_scene_id=job_context.scene_id,
                    )
                    proposed = self._steward.propose_delta(delta)
                    result = self._steward.validate_delta(proposed, current_bible)
                    if not result.valid:
                        logger.warning(
                            "ContinuityAgent: bible contradiction in scene %s — %s: %s",
                            job_context.scene_id,
                            result.contradiction_type,
                            result.detail,
                        )
                        bible_contradiction = True
                        break
                except Exception as exc:
                    logger.error("ContinuityAgent: delta validation error: %s", exc)
                    bible_contradiction = True
                    break

        # 2. Check promise deadlines for this chapter
        overdue_promises = self._tracker.enforce_promise_deadlines(job_context.chapter_id)
        overdue = [op.promise_id for op in overdue_promises]
        if overdue:
            logger.info(
                "ContinuityAgent: %d overdue promises for chapter %d: %s",
                len(overdue),
                job_context.chapter_id,
                overdue,
            )

        return dataclasses.replace(
            job_context,
            bible_contradiction=bible_contradiction,
            overdue_promises=overdue,
        )
