"""PacingAgent — evaluates rhythm, scene mix, and running pacing metrics."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, Field

from pipeline.agents.specialist_support import load_memory, save_memory, scene_text
from pipeline.core.base_agent import BaseAgent
from pipeline.core.job_context import JobContext

if TYPE_CHECKING:
    from pipeline.core.agent_context import AgentContext
    from pipeline.core.model_router import ModelRouter

logger = logging.getLogger(__name__)


class PacingAgentOutput(BaseModel):
    scene_id: str = ""
    rhythm_status: str = "balanced"
    consecutive_same_type: int = 0
    pacing_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    passed: bool = True
    notes: str = ""


class PacingAgent(BaseAgent):
    """Audits scene rhythm against SceneRhythmLedger and running book metrics."""

    impl_class: ClassVar[str] = "hybrid"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router
        load_memory(ctx, "PacingAgent")

    def _execute(self, job_context: JobContext) -> JobContext:
        text = scene_text(job_context)
        scene_type = str(job_context.output_data.get("_scene_type", "unknown"))
        recent_types = self.ctx.ledger_manager.scene_rhythm.recent_types()
        consecutive = self.ctx.ledger_manager.scene_rhythm.consecutive_count(scene_type)
        totals = self.ctx.ledger_manager.book_metrics.compute_running_totals()

        output: PacingAgentOutput = self._router.call(
            messages=[
                {
                    "role": "system",
                    "content": "You are PacingAgent. Audit scene rhythm and pacing.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Scene: {job_context.scene_id}\nScene type: {scene_type}\n"
                        f"Recent scene rhythm: {recent_types}\n"
                        f"Consecutive same type: {consecutive}\n"
                        f"Running interiority: {totals.interiority_pct_running:.3f}\n"
                        f"Running dialogue ratio: {totals.dialogue_ratio_running:.3f}\n\n"
                        f"{text[:4000]}"
                    ),
                },
            ],
            response_model=PacingAgentOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="pacing_agent",
        )
        output = PacingAgentOutput(
            scene_id=job_context.scene_id,
            rhythm_status=output.rhythm_status,
            consecutive_same_type=consecutive,
            pacing_issues=output.pacing_issues,
            recommendations=output.recommendations,
            passed=output.passed and consecutive < 5,
            notes=output.notes,
        )
        save_memory(self.ctx, "PacingAgent", job_context.scene_id, {"passed": output.passed})
        logger.info("PacingAgent: scene=%s passed=%s", job_context.scene_id, output.passed)
        return job_context.with_output("pacing_agent", output.model_dump())
