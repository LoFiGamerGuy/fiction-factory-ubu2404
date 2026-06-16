"""EditorAgent — scans and edits a dirty draft.

Phase 1: deterministic NoFlyScanner + StructuralAnalyzer.
Phase 2: surgical LLM edit loop when violations remain.
Integrates with VoiceProfile forbidden_constructions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, Field

from pipeline.agents.agent_models import EditorOutput
from pipeline.agents.scanner import NoFlyScanner
from pipeline.agents.structural_analysis import StructuralAnalyzer
from pipeline.core.base_agent import BaseAgent
from pipeline.core.job_context import JobContext

if TYPE_CHECKING:
    from pipeline.core.agent_context import AgentContext
    from pipeline.core.model_router import ModelRouter

logger = logging.getLogger(__name__)

_MAX_SURGICAL_LOOPS = 3
_SCENE_WORD_TARGET_MIN_RATIO = 0.90


class _SurgicalEditOutput(BaseModel):
    edited_text: str = Field(description="The corrected scene prose.")


class EditorAgent(BaseAgent):
    """Runs scanner, structural analysis, and surgical LLM edits.

    Supports Claude Managed Agents (Dreaming) for persistent memory
    across editing sessions (if enabled in AgentContext).
    """

    impl_class: ClassVar[str] = "hybrid"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router
        self._scanner = NoFlyScanner()
        self._structural = StructuralAnalyzer()
        self._load_persistent_memory()

    def _execute(self, job_context: JobContext) -> JobContext:
        writer_data = job_context.output_data.get("writer_agent", {})
        text: str = writer_data.get("draft_text", "")

        if not text:
            draft_path = self.ctx.project_layout.scene_draft_path(
                job_context.chapter_id, job_context.scene_id
            )
            if draft_path.exists():
                text = draft_path.read_text(encoding="utf-8")
            else:
                logger.warning("EditorAgent: no draft text found for %s", job_context.scene_id)

        # ── Phase 1: VoiceProfile forbidden constructions ─────────────────
        if self.ctx.voice_exemplar_manager is None and hasattr(self.ctx, "spec_loader"):
            pass  # voice profile checked separately
        forbidden_violations = self._check_forbidden(text, job_context)
        if forbidden_violations:
            logger.info("EditorAgent: %d forbidden constructions found", len(forbidden_violations))

        # ── Phase 2: NoFly scan + surgical edit loop ──────────────────────
        scan_report = self._scanner.scan(text)
        loop_count = 0

        while not scan_report.is_clean and loop_count < _MAX_SURGICAL_LOOPS:
            loop_count += 1
            text = self._surgical_edit(
                text, scan_report.get_violation_phrases_for_prompt(), job_context
            )
            scan_report = self._scanner.scan(text)

        # ── Phase 3: Structural analysis ──────────────────────────────────
        struct_report = self._structural.analyze(text)
        if not struct_report.is_clean:
            text = self._surgical_edit(text, struct_report.get_issues_for_prompt(), job_context)
            struct_report = self._structural.analyze(text)
            scan_report = self._scanner.scan(text)
            for _cleanup in range(2):
                if scan_report.is_clean:
                    break
                text = self._surgical_edit(
                    text, scan_report.get_violation_phrases_for_prompt(), job_context
                )
                scan_report = self._scanner.scan(text)

        is_clean = scan_report.is_clean and struct_report.is_clean
        output = EditorOutput(
            edited_text=text,
            nofly_violations=scan_report.total_violations,
            structural_flags=struct_report.total,
            structural_weighted_score=struct_report.weighted_score(),
            edit_passes=loop_count,
            is_clean=is_clean,
        )

        edited_path = self.ctx.project_layout.scene_output_path(
            job_context.chapter_id, job_context.scene_id
        )
        edited_path.parent.mkdir(parents=True, exist_ok=True)
        edited_path.write_text(text, encoding="utf-8")

        logger.info(
            "EditorAgent: nofly=%d structural=%d (clean=%s)",
            output.nofly_violations,
            output.structural_flags,
            output.is_clean,
        )

        # Save persistent memory if Dreaming enabled
        self._save_persistent_memory(output)

        return job_context.with_output("editor_agent", output.model_dump())

    def _check_forbidden(self, text: str, job_context: JobContext) -> list[str]:
        try:
            voice_data = job_context.output_data.get("_voice_profile", {})
            forbidden = voice_data.get("forbidden_constructions_raw", [])
            if not forbidden or not isinstance(forbidden, list):
                return []
            import re

            hits: list[str] = []
            for pattern_str in forbidden:
                try:
                    if re.search(pattern_str, text, re.IGNORECASE):
                        hits.append(pattern_str)
                except re.error:
                    pass
            return hits
        except Exception:
            return []

    def _surgical_edit(self, text: str, issues_prompt: str, job_context: JobContext) -> str:
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a precision editor. Fix ONLY the listed issues. "
                        "Do not change anything else. Preserve all prose, structure, and voice."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{issues_prompt}\n\n"
                        f"## Original text to fix:\n{text}\n\n"
                        "Return the corrected text only."
                    ),
                },
            ]
            result: _SurgicalEditOutput = self._router.call(
                messages=messages,
                response_model=_SurgicalEditOutput,
                provider=self.ctx.llm_provider,
                seed=job_context.seed,
                max_tokens=max(len(text.split()) * 2, 2048),
                job_id=job_context.job_id,
                agent_id="editor_agent",
            )
            edited_text = result.edited_text or text
            if _structural_edit_shrinks_below_minimum(
                text, edited_text, issues_prompt, job_context
            ):
                logger.warning(
                    "EditorAgent: rejected structural edit that shrank scene below minimum "
                    "word count (scene=%s)",
                    job_context.scene_id,
                )
                return text
            return edited_text
        except Exception as exc:
            logger.warning("EditorAgent surgical edit failed (non-fatal): %s", exc)
            return text

    # ── Persistent Memory (Claude Managed Agents / Dreaming) ──────────────

    def _load_persistent_memory(self) -> None:
        """Load persistent memory if Dreaming enabled."""
        if not self.ctx.managed_agent_config or not self.ctx.managed_agent_config.dreaming_enabled:
            return

        memory_path = self.ctx.managed_agent_config.get_memory_file("EditorAgent")
        if not memory_path.exists():
            logger.debug("EditorAgent: no persistent memory found (first run)")
            return

        try:
            import json

            memory_data = json.loads(memory_path.read_text(encoding="utf-8"))
            logger.info(
                "EditorAgent: loaded memory (scenes_edited=%d, total_surgical_passes=%d)",
                memory_data.get("scenes_edited", 0),
                memory_data.get("total_surgical_passes", 0),
            )
        except Exception as exc:
            logger.warning("EditorAgent: failed to load memory: %s", exc)

    def _save_persistent_memory(self, edit_output: EditorOutput) -> None:
        """Save persistent memory if Dreaming enabled."""
        if not self.ctx.managed_agent_config or not self.ctx.managed_agent_config.dreaming_enabled:
            return

        memory_path = self.ctx.managed_agent_config.get_memory_file("EditorAgent")
        memory_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import json

            existing = {}
            if memory_path.exists():
                existing = json.loads(memory_path.read_text(encoding="utf-8"))

            # Update counters
            existing["scenes_edited"] = existing.get("scenes_edited", 0) + 1
            existing["total_surgical_passes"] = (
                existing.get("total_surgical_passes", 0) + edit_output.edit_passes
            )
            existing["total_nofly_violations"] = (
                existing.get("total_nofly_violations", 0) + edit_output.nofly_violations
            )
            existing["total_structural_flags"] = (
                existing.get("total_structural_flags", 0) + edit_output.structural_flags
            )

            # Track last 10 scenes
            if "recent_scenes" not in existing:
                existing["recent_scenes"] = []
            existing["recent_scenes"].append(
                {
                    "nofly": edit_output.nofly_violations,
                    "structural": edit_output.structural_flags,
                    "passes": edit_output.edit_passes,
                    "clean": edit_output.is_clean,
                }
            )
            existing["recent_scenes"] = existing["recent_scenes"][-10:]

            memory_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            logger.debug("EditorAgent: saved memory (%d scenes)", existing["scenes_edited"])
        except Exception as exc:
            logger.warning("EditorAgent: failed to save memory: %s", exc)


def _structural_edit_shrinks_below_minimum(
    original_text: str,
    edited_text: str,
    issues_prompt: str,
    job_context: JobContext,
) -> bool:
    if not issues_prompt.startswith("STRUCTURAL ISSUES TO ADDRESS"):
        return False
    minimum_words = _minimum_scene_word_count(job_context.word_count_target)
    if minimum_words <= 0:
        return False
    return _word_count(original_text) >= minimum_words and _word_count(edited_text) < minimum_words


def _minimum_scene_word_count(word_target: int) -> int:
    if word_target <= 0:
        return 0
    return max(1, round(word_target * _SCENE_WORD_TARGET_MIN_RATIO))


def _word_count(text: str) -> int:
    return len(text.split()) if text else 0
