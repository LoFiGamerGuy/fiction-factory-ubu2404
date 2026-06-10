"""JobRunner — thin orchestrator over SceneStateMachine.

Builds the initial SceneState from a JobContext and wires up all agents.
Integrates TraceCollector for EvoSkill learning (Phase 12).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.agents.quality_agent import QualityAgent
from pipeline.agents.writer_agent import WriterAgent
from pipeline.continuity.bible_steward import BibleSteward
from pipeline.continuity.continuity_agent import ContinuityAgent
from pipeline.continuity.loop_tracker import LoopTracker
from pipeline.continuity.series_arc_tracker import SeriesArcTracker
from pipeline.control.wuphf_client import WUPHFClient
from pipeline.convergence_controller import ConvergenceController
from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
from pipeline.core.model_router import ModelRouter
from pipeline.dashboard_events import (
    append_quality_gate_event,
    append_run_event,
    utc_now,
    write_run_state,
)
from pipeline.evoskill.trace_collector import TraceCollector
from pipeline.scene_state_machine import SceneState, SceneStateMachine

logger = logging.getLogger(__name__)


@dataclass
class SceneRunResult:
    scene_id: str
    job_id: str
    thread_id: str
    final_text: str
    force_resolved: bool
    convergence_decision: str
    revise_count: int
    error: str
    final_state: SceneState


class JobRunner:
    """Runs a single scene through the full pipeline state machine."""

    def __init__(
        self,
        agent_ctx: AgentContext,
        model_router: ModelRouter,
        max_revisions: int = 3,
        checkpoint_db_path: str | None = None,
        trace_collector: TraceCollector | None = None,
    ) -> None:
        self._ctx = agent_ctx
        self._router = model_router
        self._max_revisions = max_revisions
        self._checkpoint_db = checkpoint_db_path
        data_root = getattr(agent_ctx.ledger_manager, "data_root", Path("data"))
        self._data_root = Path(data_root)
        self._trace_collector = trace_collector or TraceCollector(data_root=data_root)

        from pipeline.agents.editor_agent import EditorAgent

        self._writer = WriterAgent(ctx=agent_ctx, model_router=model_router)
        self._editor = EditorAgent(ctx=agent_ctx, model_router=model_router)
        self._quality = QualityAgent(ctx=agent_ctx)
        self._continuity = ContinuityAgent(
            ctx=agent_ctx,
            bible_steward=BibleSteward(
                agent_ctx.project_layout.bible_state_dir(),
                wuphf_client=WUPHFClient(),
                series_id=agent_ctx.project_layout.series_root.name,
            ),
            loop_tracker=LoopTracker(
                promise_ledger=agent_ctx.ledger_manager.promise,
                series_promise_ledger=agent_ctx.ledger_manager.series_promise,
            ),
        )
        self._series_arc_tracker = SeriesArcTracker(agent_ctx.ledger_manager.series_promise)
        self._controller = ConvergenceController(max_revisions=max_revisions)

    def run_scene(self, job_context: JobContext) -> SceneRunResult:
        """Execute a complete scene lifecycle and return SceneRunResult."""
        agents: dict[str, Any] = {
            "writer_agent": self._writer,
            "editor_agent": self._editor,
            "continuity_agent": self._continuity,
            "series_arc_tracker": self._series_arc_tracker,
            "quality_agent": self._quality,
        }

        def _make_job_context(state: SceneState) -> JobContext:
            merged_output: dict[str, Any] = dict(job_context.output_data)
            if state.get("writer_output"):
                merged_output["writer_agent"] = state["writer_output"]
            if state.get("editor_output"):
                merged_output["editor_agent"] = state["editor_output"]
            if state.get("quality_output"):
                merged_output["quality_agent"] = state["quality_output"]
            return JobContext(
                job_id=state["job_id"],
                series_id=state["series_id"],
                book_id=state["book_id"],
                chapter_id=state["chapter_id"],
                scene_id=state["scene_id"],
                spec=job_context.spec,
                model_tier=state["model_tier"],
                seed=state["seed"],
                scene_brief=state["scene_brief"],
                word_count_target=state["word_count_target"],
                heat_level=state["heat_level"],
                final_text=state.get("final_text", ""),
                bible_contradiction=state.get("bible_contradiction", False),
                overdue_promises=state.get("overdue_promises", []),
                output_data=merged_output,
            )

        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_make_job_context,
            controller=self._controller,
            checkpoint_db_path=self._checkpoint_db,
        )

        initial: SceneState = {
            "job_id": job_context.job_id,
            "scene_id": job_context.scene_id,
            "book_id": job_context.book_id,
            "series_id": job_context.series_id,
            "chapter_id": job_context.chapter_id,
            "model_tier": job_context.model_tier,
            "seed": job_context.seed,
            "scene_brief": job_context.scene_brief,
            "word_count_target": job_context.word_count_target,
            "heat_level": job_context.heat_level,
            "writer_output": {},
            "editor_output": {},
            "quality_output": {},
            "convergence_decision": "",
            "revise_count": 0,
            "final_text": "",
            "force_resolved": False,
            "force_resolve_reason": "",
            "bible_contradiction": job_context.bible_contradiction,
            "overdue_promises": job_context.overdue_promises,
            "error": "",
        }

        logger.info(
            "JobRunner: starting scene %s (job=%s)", job_context.scene_id, job_context.job_id
        )
        thread_id = job_context.job_id
        self._emit_dashboard_start(job_context, thread_id)
        try:
            final_state = machine.run(initial, thread_id=thread_id)
        finally:
            machine.close()
        logger.info(
            "JobRunner: finished scene %s decision=%s",
            job_context.scene_id,
            final_state.get("convergence_decision", "?"),
        )

        # Phase 12: collect trace for EvoSkill learning after scene completion.
        # Fail-safe: trace collection failure does not break scene execution.
        self._collect_trace_safe(job_context, final_state)
        self._emit_dashboard_finish(job_context, thread_id, final_state)

        return SceneRunResult(
            scene_id=job_context.scene_id,
            job_id=job_context.job_id,
            thread_id=thread_id,
            final_text=final_state.get("final_text", ""),
            force_resolved=final_state.get("force_resolved", False),
            convergence_decision=final_state.get("convergence_decision", ""),
            revise_count=final_state.get("revise_count", 0),
            error=final_state.get("error", ""),
            final_state=final_state,
        )

    def _emit_dashboard_start(self, job_context: JobContext, thread_id: str) -> None:
        event = {
            "event": "run_started",
            "run_id": job_context.job_id,
            "thread_id": thread_id,
            "book_id": job_context.book_id,
            "scene_id": job_context.scene_id,
            "active_scene": job_context.scene_id,
            "current_agent": "writer_agent",
            "routing_decision": "",
            "status": "running",
            "created_at": utc_now(),
        }
        write_run_state(self._data_root, job_context.job_id, event)
        append_run_event(self._data_root, job_context.job_id, event)

    def _emit_dashboard_finish(
        self,
        job_context: JobContext,
        thread_id: str,
        final_state: SceneState,
    ) -> None:
        decision = final_state.get("convergence_decision", "")
        event = {
            "event": "run_finished",
            "run_id": job_context.job_id,
            "thread_id": thread_id,
            "book_id": job_context.book_id,
            "scene_id": job_context.scene_id,
            "active_scene": job_context.scene_id,
            "current_agent": "final",
            "routing_decision": decision,
            "decision": decision,
            "status": "completed" if not final_state.get("error") else "error",
            "force_resolved": final_state.get("force_resolved", False),
            "revise_count": final_state.get("revise_count", 0),
            "created_at": utc_now(),
        }
        write_run_state(self._data_root, job_context.job_id, event)
        append_run_event(self._data_root, job_context.job_id, event)
        append_quality_gate_event(self._data_root, job_context.book_id, event)

    def _collect_trace_safe(
        self,
        job_context: JobContext,
        final_state: SceneState,
    ) -> None:
        """Collect and save EvoSkill trace after scene completion (fail-safe).

        Trace collection failure logs a warning but does not raise or break
        the scene execution path (DEC-000-8: heavier-weight, fail-closed).
        """
        try:
            # Preserve revision history: a final GO after REVISE is still a failure trace.
            routing_decisions: list[str] = [
                "REVISE" for _ in range(int(final_state.get("revise_count", 0) or 0))
            ]
            decision = final_state.get("convergence_decision", "")
            if decision:
                routing_decisions.append(decision)

            # Extract quality_scores if available from quality_output
            quality_scores: dict[str, float] = {}
            critic_scores: dict[str, float] = {}
            quality_output = final_state.get("quality_output", {})
            if isinstance(quality_output, dict):
                # QualityResult may have tier or needs_review fields
                if "tier" in quality_output:
                    quality_scores["tier_score"] = 1.0 if quality_output["tier"] == "pass" else 0.0
                if "needs_review" in quality_output:
                    quality_scores["needs_review"] = 1.0 if quality_output["needs_review"] else 0.0
                raw_critic_scores = quality_output.get("critic_scores")
                if isinstance(raw_critic_scores, dict):
                    critic_scores = {
                        str(key): float(value)
                        for key, value in raw_critic_scores.items()
                        if isinstance(value, int | float)
                    }

            # Build updated JobContext with final scene state for trace collection
            trace_job_context = JobContext(
                job_id=job_context.job_id,
                series_id=job_context.series_id,
                book_id=job_context.book_id,
                chapter_id=job_context.chapter_id,
                scene_id=job_context.scene_id,
                spec=job_context.spec,
                model_tier=job_context.model_tier,
                seed=job_context.seed,
                scene_brief=job_context.scene_brief,
                word_count_target=job_context.word_count_target,
                heat_level=job_context.heat_level,
                final_text=final_state.get("final_text", ""),
                bible_contradiction=final_state.get("bible_contradiction", False),
                overdue_promises=final_state.get("overdue_promises", []),
                output_data={
                    "writer_agent": final_state.get("writer_output", {}),
                    "editor_agent": final_state.get("editor_output", {}),
                    "quality_agent": final_state.get("quality_output", {}),
                },
            )

            trace = self._trace_collector.collect_scene_trace(
                job_context=trace_job_context,
                routing_decisions=routing_decisions,
                quality_scores=quality_scores,
                critic_scores=critic_scores,
            )

            self._trace_collector.save_trace(trace)

            logger.info(
                "JobRunner: saved %s trace for scene %s (mode=%s)",
                trace.trace_type,
                job_context.scene_id,
                trace.failure_mode or "success",
            )
        except Exception as exc:
            # Fail-safe: log warning but do not raise or break scene execution
            logger.warning(
                "JobRunner: trace collection failed for scene %s: %s",
                job_context.scene_id,
                exc,
                exc_info=True,
            )

    def resume(self, thread_id: str, job_context: JobContext) -> SceneRunResult | None:
        """Resume a checkpointed scene run."""
        if not self._checkpoint_db:
            return None

        agents: dict[str, Any] = {
            "writer_agent": self._writer,
            "editor_agent": self._editor,
            "continuity_agent": self._continuity,
            "series_arc_tracker": self._series_arc_tracker,
            "quality_agent": self._quality,
        }

        def _make_job_context(state: SceneState) -> JobContext:
            return job_context

        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_make_job_context,
            controller=self._controller,
            checkpoint_db_path=self._checkpoint_db,
        )
        try:
            final_state = machine.resume(thread_id)
        finally:
            machine.close()
        if final_state is None:
            return None

        return SceneRunResult(
            scene_id=job_context.scene_id,
            job_id=job_context.job_id,
            thread_id=thread_id,
            final_text=final_state.get("final_text", ""),
            force_resolved=final_state.get("force_resolved", False),
            convergence_decision=final_state.get("convergence_decision", ""),
            revise_count=final_state.get("revise_count", 0),
            error=final_state.get("error", ""),
            final_state=final_state,
        )
