"""ConvergenceController — routing decisions for scene generation loop.

Decision hierarchy (evaluated in order):
  1. Sensitivity violation          → RE_PLAN  (hard-coded; never FORCE_RESOLVE)
  2. Bible contradiction            → RE_PLAN  (Phase 9)
  3. Overdue promises + room left   → REVISE   (Phase 9)
  4. needs_review + under revision limit → REVISE
  5. needs_review + at revision limit    → RE_PLAN
  6. Budget exhausted               → FORCE_RESOLVE + mandatory log
  7. All gates passed               → GO

Never returns a halt/wait. Always terminates.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pipeline.agents.agent_models import QualityResult
from pipeline.core.job_context import JobContext

logger = logging.getLogger(__name__)


class ConvergenceDecision(str, Enum):
    GO = "GO"
    REVISE = "REVISE"
    RE_PLAN = "RE_PLAN"
    FORCE_RESOLVE = "FORCE_RESOLVE"


class ConvergenceController:
    """Decides the next routing step after quality evaluation."""

    def __init__(
        self,
        max_revisions: int = 3,
        budget_words_threshold: int = 0,
        decisions_log_path: Path | None = None,
    ) -> None:
        self._max_revisions = max_revisions
        self._budget_threshold = budget_words_threshold
        self._log_path = decisions_log_path

    def decide(
        self,
        quality_result: QualityResult,
        job_context: JobContext,
        revise_count: int = 0,
    ) -> ConvergenceDecision:
        """Return the next routing decision. Never raises."""
        # 1. Sensitivity violation → RE_PLAN (DEC-005; hard-coded, cannot FORCE-RESOLVE)
        if quality_result.sensitivity_violation:
            logger.warning(
                "ConvergenceController: sensitivity violation → RE_PLAN (scene=%s)",
                job_context.scene_id,
            )
            return ConvergenceDecision.RE_PLAN

        # 2. Bible contradiction → RE_PLAN (Phase 9 integration)
        if job_context.bible_contradiction:
            logger.warning(
                "ConvergenceController: bible contradiction → RE_PLAN (scene=%s)",
                job_context.scene_id,
            )
            return ConvergenceDecision.RE_PLAN

        # 3. Overdue promises + revisions remaining → REVISE (Phase 9)
        if job_context.overdue_promises and revise_count < self._max_revisions:
            logger.info(
                "ConvergenceController: overdue promises → REVISE (scene=%s, attempt=%d)",
                job_context.scene_id,
                revise_count + 1,
            )
            return ConvergenceDecision.REVISE

        # 4. Quality needs review + under limit → REVISE
        if quality_result.needs_review and revise_count < self._max_revisions:
            logger.info(
                "ConvergenceController: quality gate → REVISE (scene=%s, attempt=%d/%d)",
                job_context.scene_id,
                revise_count + 1,
                self._max_revisions,
            )
            return ConvergenceDecision.REVISE

        # 5. Quality still needs review at limit → RE_PLAN
        if quality_result.needs_review and revise_count >= self._max_revisions:
            logger.warning(
                "ConvergenceController: max revisions exhausted → RE_PLAN (scene=%s)",
                job_context.scene_id,
            )
            return ConvergenceDecision.RE_PLAN

        # 6. Budget exhausted → FORCE_RESOLVE + mandatory log
        if self._is_budget_exhausted(job_context):
            self._log_force_resolve(job_context, reason="word_count_budget_exhausted")
            return ConvergenceDecision.FORCE_RESOLVE

        # 7. All good → GO
        return ConvergenceDecision.GO

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_budget_exhausted(self, job_context: JobContext) -> bool:
        quality_data = job_context.output_data.get("quality_agent", {})
        remaining = quality_data.get("word_count_remaining", None)
        if remaining is not None:
            return int(remaining) <= self._budget_threshold
        return False

    def _log_force_resolve(self, job_context: JobContext, reason: str) -> None:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": "FORCE_RESOLVE",
            "reason": reason,
            "job_id": job_context.job_id,
            "scene_id": job_context.scene_id,
            "book_id": job_context.book_id,
        }
        logger.warning(
            "ConvergenceController: FORCE_RESOLVE logged (scene=%s reason=%s)",
            job_context.scene_id,
            reason,
        )
        if self._log_path:
            try:
                self._log_path.parent.mkdir(parents=True, exist_ok=True)
                with self._log_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry) + "\n")
            except OSError as exc:
                logger.error("ConvergenceController: failed to write FORCE_RESOLVE log: %s", exc)
