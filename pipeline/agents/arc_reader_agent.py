"""ArcReaderAgent — assesses character arc progression for the current scene."""

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


class ArcReaderOutput(BaseModel):
    scene_id: str = ""
    arc_positions: dict[str, str] = Field(default_factory=dict)
    arc_momentum: str = "flat"  # advancing | retreating | flat
    blocking_issues: list[str] = Field(default_factory=list)
    notes: str = ""


class ArcReaderAgent(BaseAgent):
    """Reads character arc state and assesses scene-level arc progression."""

    impl_class: ClassVar[str] = "llm"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router

    def _execute(self, job_context: JobContext) -> JobContext:
        edited_text = job_context.output_data.get("editor_agent", {}).get("edited_text", "")
        arc_events = self.ctx.ledger_manager.character_arc._all_payloads()
        char_ids = sorted({e["character_id"] for e in arc_events})
        arc_summary = ", ".join(
            f"{cid}={self.ctx.ledger_manager.character_arc.get_arc_position(cid)}"
            for cid in char_ids[:5]
        )

        messages = [
            {
                "role": "system",
                "content": "You are a developmental editor assessing character arc progression.",
            },
            {
                "role": "user",
                "content": (
                    f"Scene: {job_context.scene_id}\n"
                    f"Current arc positions: {arc_summary or 'none yet'}\n\n"
                    f"Scene text:\n{edited_text[:3000]}\n\n"
                    "Assess arc progression for each character in this scene."
                ),
            },
        ]

        output: ArcReaderOutput = self._router.call(
            messages=messages,
            response_model=ArcReaderOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="arc_reader_agent",
        )
        output = ArcReaderOutput(
            scene_id=job_context.scene_id,
            arc_positions=output.arc_positions,
            arc_momentum=output.arc_momentum,
            blocking_issues=output.blocking_issues,
            notes=output.notes,
        )
        logger.info(
            "ArcReaderAgent: momentum=%s blocking=%d",
            output.arc_momentum,
            len(output.blocking_issues),
        )
        return job_context.with_output("arc_reader_agent", output.model_dump())
