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
    """Decides the next routing step after quality evaluation.

    Supports Claude Managed Agents (Dreaming) for persistent memory
    of routing decisions across scenes (if enabled).
    """

    def __init__(
        self,
        max_revisions: int = 3,
        budget_words_threshold: int = 0,
        decisions_log_path: Path | None = None,
        managed_agent_config: Any = None,  # ManagedAgentConfig | None
    ) -> None:
        self._max_revisions = max_revisions
        self._budget_threshold = budget_words_threshold
        self._log_path = decisions_log_path
        self._managed_config = managed_agent_config
        self._load_persistent_memory()

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
            decision = ConvergenceDecision.RE_PLAN
            self._save_persistent_memory(
                decision, job_context, revise_count, "sensitivity_violation"
            )
            return decision

        # 2. Bible contradiction → RE_PLAN (Phase 9 integration)
        if job_context.bible_contradiction:
            logger.warning(
                "ConvergenceController: bible contradiction → RE_PLAN (scene=%s)",
                job_context.scene_id,
            )
            decision = ConvergenceDecision.RE_PLAN
            self._save_persistent_memory(decision, job_context, revise_count, "bible_contradiction")
            return decision

        # 3. Overdue promises + revisions remaining → REVISE (Phase 9)
        if job_context.overdue_promises and revise_count < self._max_revisions:
            logger.info(
                "ConvergenceController: overdue promises → REVISE (scene=%s, attempt=%d)",
                job_context.scene_id,
                revise_count + 1,
            )
            decision = ConvergenceDecision.REVISE
            self._save_persistent_memory(decision, job_context, revise_count, "overdue_promises")
            return decision

        # 4. Quality needs review + under limit → REVISE
        if quality_result.needs_review and revise_count < self._max_revisions:
            logger.info(
                "ConvergenceController: quality gate → REVISE (scene=%s, attempt=%d/%d)",
                job_context.scene_id,
                revise_count + 1,
                self._max_revisions,
            )
            decision = ConvergenceDecision.REVISE
            self._save_persistent_memory(
                decision, job_context, revise_count, "quality_needs_review"
            )
            return decision

        # 5. Quality still needs review at limit → RE_PLAN
        if quality_result.needs_review and revise_count >= self._max_revisions:
            logger.warning(
                "ConvergenceController: max revisions exhausted → RE_PLAN (scene=%s)",
                job_context.scene_id,
            )
            decision = ConvergenceDecision.RE_PLAN
            self._save_persistent_memory(decision, job_context, revise_count, "revisions_exhausted")
            return decision

        # 6. Budget exhausted → FORCE_RESOLVE + mandatory log
        if self._is_budget_exhausted(job_context):
            self._log_force_resolve(job_context, reason="word_count_budget_exhausted")
            decision = ConvergenceDecision.FORCE_RESOLVE
            self._save_persistent_memory(decision, job_context, revise_count, "budget_exhausted")
            return decision

        # 7. All good → GO
        decision = ConvergenceDecision.GO
        self._save_persistent_memory(decision, job_context, revise_count, "passed")
        return decision

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

    # ── Persistent Memory (Claude Managed Agents / Dreaming) ──────────────

    def _load_persistent_memory(self) -> None:
        """Load persistent memory if Dreaming enabled."""
        if not self._managed_config or not hasattr(self._managed_config, "dreaming_enabled"):
            return
        if not self._managed_config.dreaming_enabled:
            return

        memory_file = self._managed_config.get_memory_file("ConvergenceController")
        if not memory_file.exists():
            logger.debug("ConvergenceController: no persistent memory found (first run)")
            return

        try:
            memory_data = json.loads(memory_file.read_text(encoding="utf-8"))
            logger.info(
                "ConvergenceController: loaded memory (decisions=%d, GO_rate=%.2f%%)",
                memory_data.get("total_decisions", 0),
                memory_data.get("go_rate", 0.0) * 100,
            )
        except Exception as exc:
            logger.warning("ConvergenceController: failed to load memory: %s", exc)

    def _save_persistent_memory(
        self,
        decision: ConvergenceDecision,
        job_context: JobContext,
        revise_count: int,
        reason: str,
    ) -> None:
        """Save persistent memory if Dreaming enabled."""
        if not self._managed_config or not hasattr(self._managed_config, "dreaming_enabled"):
            return
        if not self._managed_config.dreaming_enabled:
            return

        memory_file = self._managed_config.get_memory_file("ConvergenceController")
        memory_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            existing = {}
            if memory_file.exists():
                existing = json.loads(memory_file.read_text(encoding="utf-8"))

            # Update counters
            existing["total_decisions"] = existing.get("total_decisions", 0) + 1
            existing["total_GO"] = existing.get("total_GO", 0) + (
                1 if decision == ConvergenceDecision.GO else 0
            )
            existing["total_REVISE"] = existing.get("total_REVISE", 0) + (
                1 if decision == ConvergenceDecision.REVISE else 0
            )
            existing["total_RE_PLAN"] = existing.get("total_RE_PLAN", 0) + (
                1 if decision == ConvergenceDecision.RE_PLAN else 0
            )
            existing["total_FORCE_RESOLVE"] = existing.get("total_FORCE_RESOLVE", 0) + (
                1 if decision == ConvergenceDecision.FORCE_RESOLVE else 0
            )

            # Calculate GO rate (convergence efficiency)
            total = existing["total_decisions"]
            existing["go_rate"] = existing["total_GO"] / total if total > 0 else 0.0

            # Track last 20 decisions (longer window for convergence analysis)
            if "recent_decisions" not in existing:
                existing["recent_decisions"] = []
            existing["recent_decisions"].append(
                {
                    "scene_id": job_context.scene_id,
                    "decision": decision.value,
                    "reason": reason,
                    "revise_count": revise_count,
                    "timestamp": datetime.now(UTC).isoformat()[:19],  # Truncate to seconds
                }
            )
            existing["recent_decisions"] = existing["recent_decisions"][-20:]

            memory_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            logger.debug(
                "ConvergenceController: saved memory (%d decisions)", existing["total_decisions"]
            )
        except Exception as exc:
            logger.warning("ConvergenceController: failed to save memory: %s", exc)
