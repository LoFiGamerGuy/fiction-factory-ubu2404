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


class _SurgicalEditOutput(BaseModel):
    edited_text: str = Field(description="The corrected scene prose.")


class EditorAgent(BaseAgent):
    """Runs scanner, structural analysis, and surgical LLM edits."""

    impl_class: ClassVar[str] = "hybrid"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router
        self._scanner = NoFlyScanner()
        self._structural = StructuralAnalyzer()

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
                provider="anthropic",
                seed=job_context.seed,
                max_tokens=max(len(text.split()) * 2, 2048),
                job_id=job_context.job_id,
                agent_id="editor_agent",
            )
            return result.edited_text or text
        except Exception as exc:
            logger.warning("EditorAgent surgical edit failed (non-fatal): %s", exc)
            return text
