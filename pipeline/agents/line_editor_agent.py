"""LineEditorAgent — prose polish and voice refinement."""

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


class LineEditorOutput(BaseModel):
    scene_id: str = ""
    polished_text: str = ""
    changes_made: list[str] = Field(default_factory=list)


class LineEditorAgent(BaseAgent):
    """Polishes prose style and voice at the sentence/paragraph level."""

    impl_class: ClassVar[str] = "llm"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router

    def _execute(self, job_context: JobContext) -> JobContext:
        text = job_context.output_data.get("developmental_editor_agent", {}).get(
            "revised_text"
        ) or job_context.output_data.get("editor_agent", {}).get("edited_text", "")
        voice = job_context.spec.voice_axes

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a line editor. Polish prose for voice, rhythm, and clarity. "
                    f"Target: sentence length ≈{voice.sentence_length_mean:.0f} words, "
                    f"interiority ≈{voice.internal_monologue_share:.0%}."
                ),
            },
            {
                "role": "user",
                "content": f"Polish the following scene:\n\n{text[:4000]}",
            },
        ]
        output: LineEditorOutput = self._router.call(
            messages=messages,
            response_model=LineEditorOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="line_editor_agent",
        )
        return job_context.with_output("line_editor_agent", output.model_dump())
