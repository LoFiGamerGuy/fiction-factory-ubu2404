"""WriterAgent — generates a dirty draft from a scene brief.

Calls the LLM via ModelRouter+Instructor and returns a typed WriterOutput.
All path access goes through ProjectLayout (MBSE B1 fix).

BCR-20260522: Wired for Claude Managed Agents Dreaming support.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, ClassVar

from pipeline.agents.agent_models import WriterOutput
from pipeline.core.base_agent import BaseAgent
from pipeline.core.context_manager import ContextManager
from pipeline.core.context_pack_builder import ContextPackBuilder
from pipeline.core.job_context import JobContext

if TYPE_CHECKING:
    from pathlib import Path

    from pipeline.core.agent_context import AgentContext
    from pipeline.core.model_router import ModelRouter

logger = logging.getLogger(__name__)
_SCENE_WORD_TARGET_MIN_RATIO = 0.90


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

        # BCR-20260522: Persistent memory for Dreaming
        self._memory_path: Path | None = None
        if ctx.managed_agent_config and ctx.managed_agent_config.managed_agent_mode:
            self._memory_path = ctx.managed_agent_config.get_memory_file("WriterAgent")
            logger.info(
                "WriterAgent: managed_agent_mode enabled (dreaming=%s, memory=%s)",
                ctx.managed_agent_config.dreaming_enabled,
                self._memory_path,
            )

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
            prior_feedback=_prior_quality_feedback(job_context),
            previous_draft=_previous_scene_text(job_context),
        )

        output: WriterOutput = self._router.call(
            messages=messages,
            response_model=WriterOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            max_tokens=max(word_target * 3, 2048),
            job_id=job_context.job_id,
            agent_id="writer_agent",
        )

        actual_word_count = _word_count(output.draft_text)
        if output.word_count != actual_word_count or output.scene_id != job_context.scene_id:
            output = WriterOutput(
                draft_text=output.draft_text,
                word_count=actual_word_count,
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

        # BCR-20260522: Update persistent memory for Dreaming
        self._update_memory_from_output(output, job_context.scene_id)

        return job_context.with_output("writer_agent", output.model_dump())

    @staticmethod
    def _build_messages(
        scene_brief: str,
        word_target: int,
        context_bundle_dict: dict[str, Any],
        prior_feedback: list[str] | None = None,
        previous_draft: str = "",
    ) -> list[dict[str, str]]:
        series_ctx = context_bundle_dict.get("series", "")
        book_ctx = context_bundle_dict.get("book", "")
        scene_ctx = context_bundle_dict.get("scene", "")

        system = (
            "You are a skilled fiction writer. "
            "Generate a raw, emotionally immediate scene draft following the brief exactly. "
            "The requested length is binding: develop beats fully instead of summarizing them. "
            "Return ONLY one continuous scene prose draft — no commentary, no meta-text, "
            "no Markdown separators, and no alternate versions."
        )
        min_words = _minimum_scene_word_count(word_target)
        user_parts = [
            f"## Scene Brief\n{scene_brief}",
            f"Target length: {word_target} words",
            f"Minimum acceptable length: {min_words} words",
            (
                "Write a complete scene near the target length. Include concrete action, "
                "dialogue, sensory grounding, and emotional turns; do not compress the scene "
                "into a synopsis."
            ),
        ]
        feedback = [item for item in (prior_feedback or []) if str(item).strip()]
        if feedback:
            user_parts.append(
                "## Revision Feedback\n" + "\n".join(f"- {item}" for item in feedback)
            )
        if previous_draft.strip():
            previous_words = _word_count(previous_draft)
            needed_words = max(0, min_words - previous_words)
            user_parts.append(
                "## Previous Draft To Expand\n"
                f"Previous draft actual length: {previous_words} words. "
                f"Add at least {needed_words} words of concrete scene prose while revising.\n"
                f"{previous_draft.strip()}\n\n"
                "Revise and expand this draft to satisfy the target length while preserving "
                "its continuity. Replace the draft with one complete version; do not append "
                "a second version after a separator."
            )
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

    # ── Persistent memory (BCR-20260522) ──────────────────────────────────────

    def _load_memory(self) -> dict[str, Any]:
        """Load persistent memory from disk (Claude Managed Agents)."""
        if self._memory_path is None or not self._memory_path.exists():
            return {}
        try:
            data: dict[str, Any] = json.loads(self._memory_path.read_text())
            return data
        except Exception as exc:
            logger.warning("WriterAgent: failed to load memory: %s", exc)
            return {}

    def _save_memory(self, memory: dict[str, Any]) -> None:
        """Save persistent memory to disk (Claude Managed Agents)."""
        if self._memory_path is None:
            return
        try:
            self._memory_path.parent.mkdir(parents=True, exist_ok=True)
            self._memory_path.write_text(json.dumps(memory, indent=2))
            logger.debug("WriterAgent: saved memory to %s", self._memory_path)
        except Exception as exc:
            logger.warning("WriterAgent: failed to save memory: %s", exc)

    def _update_memory_from_output(self, output: WriterOutput, scene_id: str) -> None:
        """Update persistent memory with successful generation (for Dreaming)."""
        if (
            not self.ctx.managed_agent_config
            or not self.ctx.managed_agent_config.managed_agent_mode
        ):
            return

        memory = self._load_memory()

        # Track successful scenes
        if "successful_scenes" not in memory:
            memory["successful_scenes"] = []
        memory["successful_scenes"].append(
            {
                "scene_id": scene_id,
                "word_count": output.word_count,
                "timestamp": output.model_dump().get("generated_at", ""),
            }
        )

        # Keep only last 10 scenes
        memory["successful_scenes"] = memory["successful_scenes"][-10:]

        # Track total words generated
        memory["total_words_generated"] = memory.get("total_words_generated", 0) + output.word_count
        memory["scenes_completed"] = memory.get("scenes_completed", 0) + 1

        self._save_memory(memory)


def _minimum_scene_word_count(word_target: int) -> int:
    if word_target <= 0:
        return 0
    return max(1, round(word_target * _SCENE_WORD_TARGET_MIN_RATIO))


def _prior_quality_feedback(job_context: JobContext) -> list[str]:
    quality_data = job_context.output_data.get("quality_agent", {})
    notes = quality_data.get("notes", []) if isinstance(quality_data, dict) else []
    return [str(note) for note in notes if str(note).strip()]


def _previous_scene_text(job_context: JobContext) -> str:
    editor_data = job_context.output_data.get("editor_agent", {})
    if isinstance(editor_data, dict) and editor_data.get("edited_text"):
        return str(editor_data["edited_text"])
    writer_data = job_context.output_data.get("writer_agent", {})
    if isinstance(writer_data, dict) and writer_data.get("draft_text"):
        return str(writer_data["draft_text"])
    return ""


def _word_count(text: str) -> int:
    return len(text.split()) if text else 0
