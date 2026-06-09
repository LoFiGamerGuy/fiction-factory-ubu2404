"""TensionAgent — evaluates escalation, stakes, and tension continuity."""

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


class TensionAgentOutput(BaseModel):
    scene_id: str = ""
    tension_level: float = Field(default=0.5, ge=0.0, le=1.0)
    escalation_status: str = "stable"
    tension_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    passed: bool = True
    notes: str = ""


class TensionAgent(BaseAgent):
    impl_class: ClassVar[str] = "llm"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router
        load_memory(ctx, "TensionAgent")

    def _execute(self, job_context: JobContext) -> JobContext:
        dashboard = self.ctx.ledger_manager.get_dashboard_summary(
            job_context.book_id, job_context.scene_id
        )
        output: TensionAgentOutput = self._router.call(
            messages=[
                {"role": "system", "content": "You are TensionAgent. Audit stakes and escalation."},
                {
                    "role": "user",
                    "content": (
                        f"Scene: {job_context.scene_id}\nHeat level: {job_context.heat_level}\n"
                        f"Open promises: {dashboard.promises_open}\n"
                        f"Pending trope beats: {dashboard.trope_beats_pending}\n\n"
                        f"{scene_text(job_context)[:4000]}"
                    ),
                },
            ],
            response_model=TensionAgentOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="tension_agent",
        )
        output = TensionAgentOutput(
            scene_id=job_context.scene_id, **output.model_dump(exclude={"scene_id"})
        )
        save_memory(self.ctx, "TensionAgent", job_context.scene_id, {"passed": output.passed})
        logger.info("TensionAgent: scene=%s passed=%s", job_context.scene_id, output.passed)
        return job_context.with_output("tension_agent", output.model_dump())
