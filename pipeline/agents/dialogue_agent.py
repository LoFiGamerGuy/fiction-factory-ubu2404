"""DialogueAgent — audits dialogue authenticity and character voice separation."""

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


class DialogueAgentOutput(BaseModel):
    scene_id: str = ""
    dialogue_authenticity_score: float = Field(default=1.0, ge=0.0, le=1.0)
    character_voice_separation_score: float = Field(default=1.0, ge=0.0, le=1.0)
    dialogue_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    passed: bool = True
    notes: str = ""


class DialogueAgent(BaseAgent):
    impl_class: ClassVar[str] = "llm"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router
        load_memory(ctx, "DialogueAgent")

    def _execute(self, job_context: JobContext) -> JobContext:
        text = scene_text(job_context)
        character_metrics = self._recent_character_metrics()
        output: DialogueAgentOutput = self._router.call(
            messages=[
                {"role": "system", "content": "You are DialogueAgent. Audit dialogue and subtext."},
                {
                    "role": "user",
                    "content": (
                        f"Scene: {job_context.scene_id}\n"
                        f"Recent character dialogue metrics: {character_metrics}\n\n{text[:4000]}"
                    ),
                },
            ],
            response_model=DialogueAgentOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="dialogue_agent",
        )
        output = DialogueAgentOutput(
            scene_id=job_context.scene_id, **output.model_dump(exclude={"scene_id"})
        )
        save_memory(self.ctx, "DialogueAgent", job_context.scene_id, {"passed": output.passed})
        logger.info("DialogueAgent: scene=%s passed=%s", job_context.scene_id, output.passed)
        return job_context.with_output("dialogue_agent", output.model_dump())

    def _recent_character_metrics(self) -> dict[str, object]:
        events = self.ctx.ledger_manager.book_metrics._all_payloads()
        if not events:
            return {}
        metrics = events[-1].get("character_metrics", {})
        return metrics if isinstance(metrics, dict) else {}
