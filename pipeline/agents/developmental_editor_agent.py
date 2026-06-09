"""DevelopmentalEditorAgent — structure, arc, and pacing analysis."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, Field

from pipeline.core.base_agent import BaseAgent
from pipeline.core.job_context import JobContext

if TYPE_CHECKING:
    from pipeline.core.agent_context import AgentContext
    from pipeline.core.model_router import ModelRouter

logger = logging.getLogger(__name__)


class DevelopmentalEditorOutput(BaseModel):
    scene_id: str = ""
    structure_issues: list[str] = Field(default_factory=list)
    arc_issues: list[str] = Field(default_factory=list)
    pacing_issues: list[str] = Field(default_factory=list)
    revised_text: str = ""
    notes: str = ""


class DevelopmentalEditorAgent(BaseAgent):
    """Reviews and revises scene structure, arc progression, and pacing."""

    impl_class: ClassVar[str] = "llm"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router

    def _execute(self, job_context: JobContext) -> JobContext:
        text = job_context.output_data.get("editor_agent", {}).get("edited_text", "")
        arc_data = job_context.output_data.get("arc_reader_packet_agent", {})

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a developmental editor. Focus on structure, "
                    "character arc progression, and pacing."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Arc analysis: {arc_data}\n\n"
                    f"Scene (ch {job_context.chapter_id}):\n{text[:4000]}\n\n"
                    "Identify structure/arc/pacing issues. Revise if needed."
                ),
            },
        ]
        output: DevelopmentalEditorOutput = self._router.call(
            messages=messages,
            response_model=DevelopmentalEditorOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="developmental_editor_agent",
        )
        return job_context.with_output("developmental_editor_agent", output.model_dump())
