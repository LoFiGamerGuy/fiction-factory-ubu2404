"""StyleAgent — audits scene prose against voice profile and AI-tell patterns."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, Field

from pipeline.agents.scanner import NoFlyScanner
from pipeline.core.base_agent import BaseAgent
from pipeline.core.job_context import JobContext

if TYPE_CHECKING:
    from pipeline.core.agent_context import AgentContext
    from pipeline.core.model_router import ModelRouter

logger = logging.getLogger(__name__)


class StyleAgentOutput(BaseModel):
    """Structured style audit result."""

    scene_id: str = ""
    voice_alignment_score: float = Field(default=1.0, ge=0.0, le=1.0)
    ai_tell_count: int = 0
    forbidden_construction_hits: list[str] = Field(default_factory=list)
    style_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    passed: bool = True
    notes: str = ""


class StyleAgent(BaseAgent):
    """Evaluates style consistency and voice-profile compliance for a scene."""

    impl_class: ClassVar[str] = "hybrid"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext, model_router: ModelRouter) -> None:
        super().__init__(ctx)
        self._router = model_router
        self._scanner = NoFlyScanner()
        self._load_persistent_memory()

    def _execute(self, job_context: JobContext) -> JobContext:
        text = self._scene_text(job_context)
        scan_report = self._scanner.scan(text)
        forbidden_hits = self._forbidden_hits(text, job_context)
        voice_profile = job_context.output_data.get("_voice_profile", {})

        output: StyleAgentOutput = self._router.call(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are StyleAgent. Audit prose for voice-profile alignment, "
                        "AI-tell patterns, and style drift. Return only structured findings."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Scene: {job_context.scene_id}\n"
                        f"Voice profile: {voice_profile}\n"
                        f"Deterministic AI-tell count: {scan_report.total_violations}\n"
                        f"Forbidden construction hits: {forbidden_hits}\n\n"
                        f"Scene text:\n{text[:4000]}"
                    ),
                },
            ],
            response_model=StyleAgentOutput,
            provider=self.ctx.llm_provider,
            seed=job_context.seed,
            job_id=job_context.job_id,
            agent_id="style_agent",
        )

        output = StyleAgentOutput(
            scene_id=job_context.scene_id,
            voice_alignment_score=output.voice_alignment_score,
            ai_tell_count=scan_report.total_violations,
            forbidden_construction_hits=forbidden_hits,
            style_issues=output.style_issues,
            recommendations=output.recommendations,
            passed=output.passed and scan_report.is_clean and not forbidden_hits,
            notes=output.notes,
        )

        logger.info(
            "StyleAgent: scene=%s passed=%s ai_tells=%d forbidden=%d",
            job_context.scene_id,
            output.passed,
            output.ai_tell_count,
            len(output.forbidden_construction_hits),
        )
        self._save_persistent_memory(output)
        return job_context.with_output("style_agent", output.model_dump())

    @staticmethod
    def _scene_text(job_context: JobContext) -> str:
        editor_data = job_context.output_data.get("editor_agent", {})
        if isinstance(editor_data, dict):
            text = editor_data.get("edited_text", "")
            if isinstance(text, str) and text:
                return text

        writer_data = job_context.output_data.get("writer_agent", {})
        if isinstance(writer_data, dict):
            text = writer_data.get("draft_text", "")
            if isinstance(text, str):
                return text
        return job_context.final_text

    @staticmethod
    def _forbidden_hits(text: str, job_context: JobContext) -> list[str]:
        voice_data = job_context.output_data.get("_voice_profile", {})
        if not isinstance(voice_data, dict):
            return []
        raw_patterns = voice_data.get("forbidden_constructions_raw", [])
        if not isinstance(raw_patterns, list):
            return []

        hits: list[str] = []
        for pattern in raw_patterns:
            if not isinstance(pattern, str):
                continue
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    hits.append(pattern)
            except re.error:
                logger.warning("StyleAgent: invalid forbidden-construction regex: %s", pattern)
        return hits

    def _load_persistent_memory(self) -> None:
        if not self.ctx.managed_agent_config or not self.ctx.managed_agent_config.dreaming_enabled:
            return

        memory_file = self.ctx.managed_agent_config.get_memory_file("StyleAgent")
        if not memory_file.exists():
            logger.debug("StyleAgent: no persistent memory found (first run)")
            return

        try:
            memory_data: dict[str, Any] = json.loads(memory_file.read_text(encoding="utf-8"))
            logger.info(
                "StyleAgent: loaded memory (scenes_checked=%d, total_style_issues=%d)",
                memory_data.get("scenes_checked", 0),
                memory_data.get("total_style_issues", 0),
            )
        except Exception as exc:
            logger.warning("StyleAgent: failed to load memory: %s", exc)

    def _save_persistent_memory(self, output: StyleAgentOutput) -> None:
        if not self.ctx.managed_agent_config or not self.ctx.managed_agent_config.dreaming_enabled:
            return

        memory_file = self.ctx.managed_agent_config.get_memory_file("StyleAgent")
        memory_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            existing: dict[str, Any] = {}
            if memory_file.exists():
                existing = json.loads(memory_file.read_text(encoding="utf-8"))

            existing["scenes_checked"] = existing.get("scenes_checked", 0) + 1
            existing["total_style_issues"] = existing.get("total_style_issues", 0) + len(
                output.style_issues
            )
            existing["total_ai_tells"] = existing.get("total_ai_tells", 0) + output.ai_tell_count
            existing["total_forbidden_hits"] = existing.get("total_forbidden_hits", 0) + len(
                output.forbidden_construction_hits
            )

            recent = existing.setdefault("recent_scenes", [])
            recent.append(
                {
                    "scene_id": output.scene_id,
                    "passed": output.passed,
                    "voice_alignment_score": output.voice_alignment_score,
                    "ai_tell_count": output.ai_tell_count,
                    "forbidden_hits": output.forbidden_construction_hits,
                }
            )
            existing["recent_scenes"] = recent[-10:]

            memory_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            logger.debug("StyleAgent: saved memory (%d scenes)", existing["scenes_checked"])
        except Exception as exc:
            logger.warning("StyleAgent: failed to save memory: %s", exc)
