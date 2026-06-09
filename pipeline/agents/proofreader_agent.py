"""ProofreaderAgent — final error and typo check."""

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


class ProofreaderOutput(BaseModel):
    scene_id: str = ""
    proofread_text: str = ""
    errors_fixed: list[str] = Field(default_factory=list)
    is_clean: bool = True


class ProofreaderAgent(BaseAgent):
    """Final proofreading pass: typos, punctuation, formatting."""

    impl_class: ClassVar[str] = "llm"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router

    def _execute(self, job_context: JobContext) -> JobContext:
        text = job_context.output_data.get("copy_editor_agent", {}).get(
            "corrected_text"
        ) or job_context.output_data.get("editor_agent", {}).get("edited_text", "")
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a proofreader. Find and fix only typos, punctuation errors, "
                    "and formatting inconsistencies. Do not change anything else."
                ),
            },
            {"role": "user", "content": f"Proofread:\n\n{text[:4000]}"},
        ]
        output: ProofreaderOutput = self._router.call(
            messages=messages,
            response_model=ProofreaderOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="proofreader_agent",
        )
        return job_context.with_output("proofreader_agent", output.model_dump())
