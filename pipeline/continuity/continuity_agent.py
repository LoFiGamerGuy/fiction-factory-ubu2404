"""ContinuityAgent — checks bible consistency and promise deadlines before convergence.

Supports Claude Managed Agents (Dreaming) for persistent memory tracking
continuity checks across scenes.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from pipeline.continuity.bible_steward import BibleSteward
from pipeline.continuity.bible_types import BibleDelta, BibleState
from pipeline.continuity.loop_tracker import LoopTracker
from pipeline.core.base_agent import BaseAgent
from pipeline.core.job_context import JobContext
from pipeline.ledgers.bible_tracker import ContinuityEvent

if TYPE_CHECKING:
    from pipeline.core.agent_context import AgentContext

logger = logging.getLogger(__name__)


class ContinuityAgent(BaseAgent):
    """Wraps BibleSteward and LoopTracker; sets bible_contradiction and overdue_promises.

    Tracks continuity checks, contradictions found, and promise enforcement history
    via persistent memory if Dreaming enabled.
    """

    impl_class: ClassVar[str] = "hybrid"  # deterministic validation + potential LLM summarization
    version: ClassVar[str] = "1.0"

    def __init__(
        self,
        ctx: AgentContext,
        bible_steward: BibleSteward,
        loop_tracker: LoopTracker,
    ) -> None:
        super().__init__(ctx)
        self._steward = bible_steward
        self._tracker = loop_tracker
        self._load_persistent_memory()

    def _execute(self, job_context: JobContext) -> JobContext:
        """Check continuity for the current scene and annotate JobContext.

        - Validates any bible deltas embedded in output_data["bible_deltas"]
        - Checks promise deadlines for this chapter
        - Sets bible_contradiction=True if any delta is invalid
        - Populates overdue_promises with IDs of overdue open promises
        """
        bible_contradiction = False
        overdue: list[str] = []

        # 1. Validate proposed bible deltas (if any)
        pending_deltas = _extract_bible_deltas(job_context.output_data)
        if pending_deltas:
            current_bible: BibleState = self._steward._load_state(job_context.book_id)
            for raw in pending_deltas:
                try:
                    delta = _delta_from_raw(raw, job_context.scene_id)
                    proposed = self._steward.propose_delta(delta)
                    validation = self._steward.validate_delta(proposed, current_bible)
                    if not validation.valid:
                        logger.warning(
                            "ContinuityAgent: bible contradiction in scene %s — %s: %s",
                            job_context.scene_id,
                            validation.contradiction_type,
                            validation.detail,
                        )
                        self._record_continuity_event(
                            job_context=job_context,
                            delta=delta,
                            operation="contradiction_detected",
                            description=validation.detail,
                            contradiction_type=validation.contradiction_type,
                        )
                        bible_contradiction = True
                        break
                except Exception as exc:
                    logger.error("ContinuityAgent: delta validation error: %s", exc)
                    self._record_raw_contradiction_event(job_context, raw, str(exc))
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

        result = dataclasses.replace(
            job_context,
            bible_contradiction=bible_contradiction,
            overdue_promises=overdue,
        )

        self._save_persistent_memory(
            scene_id=job_context.scene_id,
            bible_contradiction=bible_contradiction,
            overdue_promises=overdue,
        )
        return result

    def commit_approved_changes(self, job_context: JobContext) -> None:
        """Commit valid bible deltas after convergence has approved the scene."""
        pending_deltas = _extract_bible_deltas(job_context.output_data)
        if not pending_deltas:
            return

        current_bible: BibleState = self._steward._load_state(job_context.book_id)
        for raw in pending_deltas:
            delta = _delta_from_raw(raw, job_context.scene_id)
            proposed = self._steward.propose_delta(delta)
            validation = self._steward.validate_delta(proposed, current_bible)
            if not validation.valid:
                self._record_continuity_event(
                    job_context=job_context,
                    delta=delta,
                    operation="contradiction_detected",
                    description=validation.detail,
                    contradiction_type=validation.contradiction_type,
                )
                raise RuntimeError(
                    f"Approved scene '{job_context.scene_id}' has invalid bible delta "
                    f"'{delta.delta_id}': {validation.detail}"
                )

            self._steward.commit_delta(proposed, job_context.book_id)
            self._record_continuity_event(
                job_context=job_context,
                delta=delta,
                operation="commit_delta",
                description=f"Committed {delta.operation} for {delta.entity_id}",
                resolved=True,
            )
            current_bible = self._steward._load_state(job_context.book_id)

    def _record_continuity_event(
        self,
        *,
        job_context: JobContext,
        delta: BibleDelta,
        operation: str,
        description: str,
        contradiction_type: str | None = None,
        resolved: bool = False,
    ) -> None:
        event = ContinuityEvent(
            event_id=str(uuid.uuid4())[:8],
            book_id=job_context.book_id,
            scene_id=job_context.scene_id,
            timestamp=datetime.now(UTC).isoformat(),
            fact_type=delta.entity_type,
            entity_id=delta.entity_id,
            operation=operation,
            description=description,
            contradiction_type=contradiction_type,
            resolved=resolved,
        )
        self.ctx.ledger_manager.bible.append(event)

    def _record_raw_contradiction_event(
        self,
        job_context: JobContext,
        raw: dict[str, Any],
        description: str,
    ) -> None:
        delta = BibleDelta(
            delta_id=str(raw.get("delta_id", "")),
            entity_id=str(raw.get("entity_id", "")),
            entity_type=str(raw.get("entity_type", "unknown")),
            operation=str(raw.get("operation", "unknown")),
            new_attributes={},
            source_scene_id=job_context.scene_id,
        )
        self._record_continuity_event(
            job_context=job_context,
            delta=delta,
            operation="contradiction_detected",
            description=description,
            contradiction_type="validation_error",
        )

    # ── Persistent Memory (Claude Managed Agents / Dreaming) ──────────────

    def _load_persistent_memory(self) -> None:
        """Load persistent memory if Dreaming enabled."""
        if not self.ctx.managed_agent_config or not self.ctx.managed_agent_config.dreaming_enabled:
            return

        memory_file = self.ctx.managed_agent_config.get_memory_file("ContinuityAgent")
        if not memory_file.exists():
            logger.debug("ContinuityAgent: no persistent memory found (first run)")
            return

        try:
            memory_data = json.loads(memory_file.read_text(encoding="utf-8"))
            logger.info(
                "ContinuityAgent: loaded memory (scenes_checked=%d, contradictions=%d)",
                memory_data.get("scenes_checked", 0),
                memory_data.get("total_contradictions", 0),
            )
        except Exception as exc:
            logger.warning("ContinuityAgent: failed to load memory: %s", exc)

    def _save_persistent_memory(
        self,
        *,
        scene_id: str,
        bible_contradiction: bool,
        overdue_promises: list[str],
    ) -> None:
        """Save persistent memory if Dreaming enabled."""
        if not self.ctx.managed_agent_config or not self.ctx.managed_agent_config.dreaming_enabled:
            return

        memory_file = self.ctx.managed_agent_config.get_memory_file("ContinuityAgent")
        memory_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            existing: dict[str, Any] = {}
            if memory_file.exists():
                existing = json.loads(memory_file.read_text(encoding="utf-8"))

            existing["scenes_checked"] = existing.get("scenes_checked", 0) + 1
            existing["total_contradictions"] = existing.get("total_contradictions", 0) + (
                1 if bible_contradiction else 0
            )
            existing["total_overdue_promise_checks"] = existing.get(
                "total_overdue_promise_checks", 0
            ) + (1 if overdue_promises else 0)

            recent = existing.setdefault("recent_scenes", [])
            recent.append(
                {
                    "scene_id": scene_id,
                    "bible_contradiction": bible_contradiction,
                    "overdue_promises": overdue_promises,
                }
            )
            existing["recent_scenes"] = recent[-10:]

            memory_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            logger.debug("ContinuityAgent: saved memory (%d scenes)", existing["scenes_checked"])
        except Exception as exc:
            logger.warning("ContinuityAgent: failed to save memory: %s", exc)


def _extract_bible_deltas(output_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect bible deltas from top-level or agent-scoped outputs."""
    deltas: list[dict[str, Any]] = []
    raw_top_level = output_data.get("bible_deltas", [])
    if isinstance(raw_top_level, list):
        deltas.extend([d for d in raw_top_level if isinstance(d, dict)])

    for agent_output in output_data.values():
        if not isinstance(agent_output, dict):
            continue
        raw_nested = agent_output.get("bible_deltas", [])
        if isinstance(raw_nested, list):
            deltas.extend([d for d in raw_nested if isinstance(d, dict)])
    return deltas


def _delta_from_raw(raw: dict[str, Any], scene_id: str) -> BibleDelta:
    return BibleDelta(
        delta_id=str(raw.get("delta_id", "")),
        entity_id=str(raw.get("entity_id", "")),
        entity_type=str(raw.get("entity_type", "character")),
        operation=str(raw.get("operation", "upsert")),
        new_attributes=raw.get("new_attributes", {}),
        timeline_event=raw.get("timeline_event"),
        source_scene_id=scene_id,
    )
