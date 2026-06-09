"""CopyEditorAgent — grammar, style consistency, and continuity corrections."""

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


class CopyEditorOutput(BaseModel):
    scene_id: str = ""
    corrected_text: str = ""
    corrections: list[str] = Field(default_factory=list)
    style_flags: list[str] = Field(default_factory=list)


class CopyEditorAgent(BaseAgent):
    """Corrects grammar, style, and consistency issues."""

    impl_class: ClassVar[str] = "llm"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router

    def _execute(self, job_context: JobContext) -> JobContext:
        text = job_context.output_data.get("line_editor_agent", {}).get(
            "polished_text"
        ) or job_context.output_data.get("editor_agent", {}).get("edited_text", "")
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a copy editor. Fix grammar, style, and consistency errors. "
                    "Do not change the voice or content."
                ),
            },
            {"role": "user", "content": f"Copy-edit:\n\n{text[:4000]}"},
        ]
        output: CopyEditorOutput = self._router.call(
            messages=messages,
            response_model=CopyEditorOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="copy_editor_agent",
        )
        return job_context.with_output("copy_editor_agent", output.model_dump())
