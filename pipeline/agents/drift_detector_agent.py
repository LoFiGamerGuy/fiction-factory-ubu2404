"""DriftDetectorAgent — detects voice drift from VoiceProfile targets."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, Field

from pipeline.core.base_agent import BaseAgent
from pipeline.core.context_manager import ContextManager
from pipeline.core.job_context import JobContext

if TYPE_CHECKING:
    from pipeline.core.agent_context import AgentContext
    from pipeline.core.model_router import ModelRouter

logger = logging.getLogger(__name__)


class DriftDetectorOutput(BaseModel):
    scene_id: str = ""
    drift_detected: bool = False
    drift_axes: list[str] = Field(default_factory=list)
    drift_scores: dict[str, float] = Field(default_factory=dict)
    recommendation: str = ""


class DriftDetectorAgent(BaseAgent):
    """Detects voice drift from VoiceProfile targets using ContextPack + LLM."""

    impl_class: ClassVar[str] = "hybrid"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router
        self._context_mgr = ContextManager(
            project_layout=ctx.project_layout,
            ledger_manager=ctx.ledger_manager,
        )

    def _execute(self, job_context: JobContext) -> JobContext:
        edited_text = job_context.output_data.get("editor_agent", {}).get("edited_text", "")
        context_bundle = self._context_mgr.assemble(job_context)
        voice_axes = job_context.spec.voice_axes

        messages = [
            {
                "role": "system",
                "content": (
                    "You detect voice drift: compare current scene against established "
                    "voice profile. "
                    f"Voice targets: interiority={voice_axes.internal_monologue_share:.0%}, "
                    f"dialogue_ratio={voice_axes.dialogue_to_narration_ratio:.0%}."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Recent book context:\n{context_bundle.book_tier[:2000]}\n\n"
                    f"Current scene:\n{edited_text[:2000]}\n\n"
                    "Identify any significant voice drift."
                ),
            },
        ]
        output: DriftDetectorOutput = self._router.call(
            messages=messages,
            response_model=DriftDetectorOutput,
            provider="anthropic",
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="drift_detector_agent",
        )
        output = DriftDetectorOutput(
            scene_id=job_context.scene_id,
            drift_detected=output.drift_detected,
            drift_axes=output.drift_axes,
            drift_scores=output.drift_scores,
            recommendation=output.recommendation,
        )
        logger.info(
            "DriftDetectorAgent: drift=%s axes=%s", output.drift_detected, output.drift_axes
        )
        return job_context.with_output("drift_detector_agent", output.model_dump())
