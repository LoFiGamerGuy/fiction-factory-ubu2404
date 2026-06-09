"""SensoryAgent — audits sensory specificity and density."""

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


class SensoryAgentOutput(BaseModel):
    scene_id: str = ""
    sensory_density_assessment: str = "adequate"
    specificity_score: float = Field(default=1.0, ge=0.0, le=1.0)
    sensory_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    passed: bool = True
    notes: str = ""


class SensoryAgent(BaseAgent):
    impl_class: ClassVar[str] = "llm"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router
        load_memory(ctx, "SensoryAgent")

    def _execute(self, job_context: JobContext) -> JobContext:
        totals = self.ctx.ledger_manager.book_metrics.compute_running_totals()
        output: SensoryAgentOutput = self._router.call(
            messages=[
                {
                    "role": "system",
                    "content": "You are SensoryAgent. Audit concrete sensory detail.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Scene: {job_context.scene_id}\n"
                        f"Running sensory density: {totals.sensory_density_running:.3f}\n\n"
                        f"{scene_text(job_context)[:4000]}"
                    ),
                },
            ],
            response_model=SensoryAgentOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="sensory_agent",
        )
        output = SensoryAgentOutput(
            scene_id=job_context.scene_id, **output.model_dump(exclude={"scene_id"})
        )
        save_memory(self.ctx, "SensoryAgent", job_context.scene_id, {"passed": output.passed})
        logger.info("SensoryAgent: scene=%s passed=%s", job_context.scene_id, output.passed)
        return job_context.with_output("sensory_agent", output.model_dump())
