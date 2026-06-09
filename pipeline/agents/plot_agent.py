"""PlotAgent — audits cause/effect, promise progress, and trope commitments."""

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


class PlotAgentOutput(BaseModel):
    scene_id: str = ""
    causality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    promise_progress: list[str] = Field(default_factory=list)
    plot_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    passed: bool = True
    notes: str = ""


class PlotAgent(BaseAgent):
    impl_class: ClassVar[str] = "llm"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router
        load_memory(ctx, "PlotAgent")

    def _execute(self, job_context: JobContext) -> JobContext:
        promises = self.ctx.ledger_manager.promise.open_promises()
        trope_beats = self.ctx.ledger_manager.trope.pending_beats()
        output: PlotAgentOutput = self._router.call(
            messages=[
                {
                    "role": "system",
                    "content": "You are PlotAgent. Audit plot causality and promise progress.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Scene: {job_context.scene_id}\nOpen promises: {promises[:5]}\n"
                        f"Pending trope beats: {trope_beats[:5]}\n\n"
                        f"{scene_text(job_context)[:4000]}"
                    ),
                },
            ],
            response_model=PlotAgentOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="plot_agent",
        )
        output = PlotAgentOutput(
            scene_id=job_context.scene_id, **output.model_dump(exclude={"scene_id"})
        )
        save_memory(self.ctx, "PlotAgent", job_context.scene_id, {"passed": output.passed})
        logger.info("PlotAgent: scene=%s passed=%s", job_context.scene_id, output.passed)
        return job_context.with_output("plot_agent", output.model_dump())
