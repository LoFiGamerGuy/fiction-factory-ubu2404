"""WriterAgent — generates a dirty draft from a scene brief.

Calls the LLM via ModelRouter+Instructor and returns a typed WriterOutput.
All path access goes through ProjectLayout (MBSE B1 fix).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from pipeline.agents.agent_models import WriterOutput
from pipeline.core.base_agent import BaseAgent
from pipeline.core.context_manager import ContextManager
from pipeline.core.context_pack_builder import ContextPackBuilder
from pipeline.core.job_context import JobContext

if TYPE_CHECKING:
    from pipeline.core.agent_context import AgentContext
    from pipeline.core.model_router import ModelRouter

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """Generates dirty drafts from scene briefs using LLM via Instructor."""

    impl_class: ClassVar[str] = "llm"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router
        self._context_mgr = ContextManager(
            project_layout=ctx.project_layout,
            ledger_manager=ctx.ledger_manager,
        )
        self._pack_builder = ContextPackBuilder(project_layout=ctx.project_layout)

    def _execute(self, job_context: JobContext) -> JobContext:
        scene_brief = job_context.scene_brief or f"Scene {job_context.scene_id}"
        word_target = job_context.word_count_target

        context_bundle = self._context_mgr.assemble(
            job_context=job_context, scene_brief=scene_brief
        )

        context_pack = self._pack_builder.build(
            job_id=job_context.job_id,
            agent_id="writer_agent",
            scene_id=job_context.scene_id,
            context_bundle=context_bundle,
        )

        messages = self._build_messages(
            scene_brief=scene_brief,
            word_target=word_target,
            context_bundle_dict=context_bundle.as_tiers_dict(),
        )

        output: WriterOutput = self._router.call(
            messages=messages,
            response_model=WriterOutput,
            provider="anthropic",
            seed=job_context.seed,
            max_tokens=max(word_target * 2, 2048),
            job_id=job_context.job_id,
            agent_id="writer_agent",
        )

        if not output.word_count:
            output = WriterOutput(
                draft_text=output.draft_text,
                word_count=len(output.draft_text.split()),
                scene_id=job_context.scene_id,
            )

        draft_path = self.ctx.project_layout.scene_draft_path(
            job_context.chapter_id, job_context.scene_id
        )
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(output.draft_text, encoding="utf-8")

        logger.info(
            "WriterAgent: %d-word draft → %s (pack=%s)",
            output.word_count,
            draft_path.name,
            context_pack.provenance_hash[:8],
        )

        return job_context.with_output("writer_agent", output.model_dump())

    @staticmethod
    def _build_messages(
        scene_brief: str,
        word_target: int,
        context_bundle_dict: dict[str, Any],
    ) -> list[dict[str, str]]:
        series_ctx = context_bundle_dict.get("series", "")
        book_ctx = context_bundle_dict.get("book", "")
        scene_ctx = context_bundle_dict.get("scene", "")

        system = (
            "You are a skilled fiction writer. "
            "Generate a raw, emotionally immediate scene draft following the brief exactly. "
            "Return ONLY the scene prose — no commentary, no meta-text."
        )
        user_parts = [f"## Scene Brief\n{scene_brief}", f"Target length: {word_target} words"]
        if series_ctx:
            user_parts.append(f"## Series Context\n{series_ctx}")
        if book_ctx:
            user_parts.append(f"## Book Context\n{book_ctx}")
        if scene_ctx:
            user_parts.append(f"## Recent History\n{scene_ctx}")

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]
