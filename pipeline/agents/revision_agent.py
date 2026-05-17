"""RevisionAgent — generates a revised draft from REVISE routing directive."""

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


class RevisionOutput(BaseModel):
    scene_id: str = ""
    revised_text: str = ""
    revision_summary: str = ""
    issues_addressed: list[str] = Field(default_factory=list)


class RevisionAgent(BaseAgent):
    """Generates a revised scene draft based on REVISE routing directives."""

    impl_class: ClassVar[str] = "llm"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router

    def _execute(self, job_context: JobContext) -> JobContext:
        text = job_context.output_data.get("editor_agent", {}).get("edited_text", "")
        quality_data = job_context.output_data.get("quality_agent", {})
        notes = quality_data.get("notes", [])
        issues_str = (
            "\n".join(f"  - {n}" for n in notes) if notes else "General quality improvement needed."
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a revision specialist. Rewrite the scene to address "
                    "the listed quality issues while preserving story beats and character voice."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Issues to address:\n{issues_str}\n\n"
                    f"Original scene:\n{text[:4000]}\n\n"
                    "Provide a revised version."
                ),
            },
        ]
        output: RevisionOutput = self._router.call(
            messages=messages,
            response_model=RevisionOutput,
            provider="anthropic",
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="revision_agent",
        )
        output = RevisionOutput(
            scene_id=job_context.scene_id,
            revised_text=output.revised_text,
            revision_summary=output.revision_summary,
            issues_addressed=output.issues_addressed,
        )
        logger.info(
            "RevisionAgent: revised scene %s (%d words)",
            job_context.scene_id,
            len(output.revised_text.split()),
        )
        return job_context.with_output("revision_agent", output.model_dump())
