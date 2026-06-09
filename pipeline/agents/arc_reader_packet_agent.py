"""ArcReaderPacketAgent — assembles a structured arc analysis packet."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, Field

from pipeline.core.base_agent import BaseAgent
from pipeline.core.job_context import JobContext

if TYPE_CHECKING:
    from pipeline.core.agent_context import AgentContext
    from pipeline.core.model_router import ModelRouter

logger = logging.getLogger(__name__)


class ArcReaderPacketOutput(BaseModel):
    scene_id: str = ""
    character_summaries: list[dict[str, Any]] = Field(default_factory=list)
    overall_arc_health: str = "healthy"  # healthy | at_risk | derailed
    recommendations: list[str] = Field(default_factory=list)


class ArcReaderPacketAgent(BaseAgent):
    """Assembles the arc analysis packet from ArcReaderAgent output."""

    impl_class: ClassVar[str] = "llm"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router

    def _execute(self, job_context: JobContext) -> JobContext:
        arc_data = job_context.output_data.get("arc_reader_agent", {})
        messages = [
            {
                "role": "system",
                "content": (
                    "You summarise arc analysis into an actionable packet for downstream agents."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Scene: {job_context.scene_id}\n"
                    f"Arc assessment: {arc_data}\n\n"
                    "Produce a structured arc packet."
                ),
            },
        ]
        output: ArcReaderPacketOutput = self._router.call(
            messages=messages,
            response_model=ArcReaderPacketOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="arc_reader_packet_agent",
        )
        return job_context.with_output("arc_reader_packet_agent", output.model_dump())
