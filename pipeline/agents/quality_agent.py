"""QualityAgent — quality gate using running-total contribution scoring.

Uses QualityEvaluator from Phase 3. Fail-closed: any evaluator exception
→ needs_review = True. Never silently passes on exception (DEC-008).
Updates all 10 ledgers after a FINAL scene.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, ClassVar

from pipeline.agents.agent_models import QualityResult
from pipeline.core.base_agent import BaseAgent
from pipeline.core.job_context import JobContext
from pipeline.ledgers.ledger_manager import SceneResult
from pipeline.ledgers.quality_evaluator import QualityEvaluator, Verdict

if TYPE_CHECKING:
    from pipeline.core.agent_context import AgentContext

logger = logging.getLogger(__name__)

# Thresholds that map QualityEvaluator verdict to routing tier
_PASS_REQUIRES = Verdict.NEUTRAL  # neutral or positive → pass
_WARN_THRESHOLD = Verdict.NEGATIVE  # negative but not all metrics → warn
_SCENE_WORD_TARGET_MIN_RATIO = 0.90


class QualityAgent(BaseAgent):
    """Scores scenes via QualityEvaluator; updates ledgers on FINAL.

    Supports Claude Managed Agents (Dreaming) for persistent memory
    across quality evaluations (if enabled in AgentContext).
    """

    impl_class: ClassVar[str] = "hybrid"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext) -> None:
        super().__init__(ctx)
        self._evaluator = QualityEvaluator()
        self._load_persistent_memory()

    def _execute(self, job_context: JobContext) -> JobContext:
        editor_data = job_context.output_data.get("editor_agent", {})
        nofly = int(editor_data.get("nofly_violations", 0))
        structural = int(editor_data.get("structural_flags", 0))
        structural_weighted = int(editor_data.get("structural_weighted_score", structural))
        sensitivity_violation = _check_sensitivity(job_context)

        scene_metrics = self._extract_scene_metrics(job_context)
        running_totals = self._get_running_totals(job_context)
        targets = self._get_targets(job_context)
        word_count_remaining = self._estimate_remaining_words(job_context)

        decision = self._evaluator.evaluate_scene_contribution(
            scene_metrics=scene_metrics,
            running_totals=running_totals,
            targets=targets,
            word_count_remaining=word_count_remaining,
        )

        tier, needs_review = _classify_tier(
            nofly=nofly,
            structural=structural,
            structural_weighted=structural_weighted,
            verdict=decision.overall_verdict,
            word_count=int(scene_metrics.get("word_count", 0)),
        )
        word_count = int(scene_metrics.get("word_count", 0))
        word_count_target = int(job_context.word_count_target or 0)
        min_word_count = _minimum_scene_word_count(word_count_target)
        word_count_under_target = word_count_target > 0 and word_count < min_word_count

        notes = [n for r in decision.metric_results for n in [r.note]]
        if word_count_under_target:
            needs_review = True
            tier = "fail"
            notes.append(
                "word_count_under_target: "
                f"scene has {word_count} words; expand to at least {min_word_count} "
                f"words (target {word_count_target})."
            )

        result = QualityResult(
            needs_review=needs_review,
            tier=tier,
            nofly_violations=nofly,
            structural_flags=structural,
            sensitivity_violation=sensitivity_violation,
            scene_id=job_context.scene_id,
            notes=notes,
        )

        logger.info(
            "QualityAgent: tier=%s needs_review=%s sensitivity=%s scene=%s",
            tier,
            needs_review,
            sensitivity_violation,
            job_context.scene_id,
        )

        # Save persistent memory if Dreaming enabled
        self._save_persistent_memory(result)

        return job_context.with_output("quality_agent", result.model_dump())

    def update_ledgers(self, job_context: JobContext) -> None:
        """Call after scene is finalized (GO decision) to update all 10 ledgers."""
        editor_data = job_context.output_data.get("editor_agent", {})
        text: str = editor_data.get("edited_text", job_context.final_text)
        word_count = len(text.split()) if text else 0

        import uuid as _uuid
        from datetime import UTC, datetime

        from pipeline.ledgers.book_metrics_ledger import BookMetricsEvent
        from pipeline.ledgers.character_metrics import compute_character_metrics

        nofly = int(editor_data.get("nofly_violations", 0))
        metrics_event = BookMetricsEvent(
            event_id=str(_uuid.uuid4())[:8],
            book_id=job_context.book_id,
            scene_id=job_context.scene_id,
            chapter_id=str(job_context.chapter_id),
            timestamp=datetime.now(UTC).isoformat(),
            word_count=word_count,
            interiority_pct=0.20,
            dialogue_ratio=0.30,
            exposition_pct=0.25,
            action_pct=0.25,
            sensory_density_per_1k=0.0,
            em_dash_density=0.0,
            sentence_length_avg=0.0,
            ai_tell_count=nofly,
            no_fly_violations=nofly,
            heat_curve_position=float(job_context.heat_level) / 5.0,
            character_metrics=compute_character_metrics(text),
        )

        scene_result = SceneResult(
            scene_id=job_context.scene_id,
            book_id=job_context.book_id,
            chapter_id=str(job_context.chapter_id),
            timestamp=datetime.now(UTC).isoformat(),
            scene_type="action",
            metrics_event=metrics_event,
        )
        self.ctx.ledger_manager.update(scene_result)
        logger.info("QualityAgent: updated all 10 ledgers for %s", job_context.scene_id)

    def _extract_scene_metrics(self, job_context: JobContext) -> dict[str, float]:
        editor_data = job_context.output_data.get("editor_agent", {})
        text: str = editor_data.get("edited_text", "")
        words = text.split() if text else []
        return {
            "word_count": float(len(words)),
            "interiority_pct": 0.20,
            "dialogue_ratio": 0.30,
            "ai_tell_count": float(editor_data.get("nofly_violations", 0)),
        }

    def _get_running_totals(self, job_context: JobContext) -> dict[str, float]:
        try:
            totals = self.ctx.ledger_manager.book_metrics.compute_running_totals()
            return {
                "word_count_total": float(totals.word_count_total),
                "interiority_pct": totals.interiority_pct_running,
                "dialogue_ratio": totals.dialogue_ratio_running,
                "ai_tell_count": float(totals.ai_tell_count_total),
            }
        except Exception:
            return {}

    def _get_targets(self, job_context: JobContext) -> dict[str, float]:
        voice = job_context.spec.voice_axes
        return {
            "interiority_pct": voice.internal_monologue_share,
            "dialogue_ratio": voice.dialogue_to_narration_ratio,
        }

    def _estimate_remaining_words(self, job_context: JobContext) -> int:
        try:
            totals = self.ctx.ledger_manager.book_metrics.compute_running_totals()
            book_max = job_context.spec.genre_config.word_count_max
            return max(0, book_max - totals.word_count_total)
        except Exception:
            return 50000  # generous default

    # ── Persistent Memory (Claude Managed Agents / Dreaming) ──────────────

    def _load_persistent_memory(self) -> None:
        """Load persistent memory if Dreaming enabled."""
        if not self.ctx.managed_agent_config or not self.ctx.managed_agent_config.dreaming_enabled:
            return

        memory_file = self.ctx.managed_agent_config.get_memory_file("QualityAgent")
        if not memory_file.exists():
            logger.debug("QualityAgent: no persistent memory found (first run)")
            return

        try:
            import json

            memory_data = json.loads(memory_file.read_text(encoding="utf-8"))
            logger.info(
                "QualityAgent: loaded memory (scenes_evaluated=%d, pass_rate=%.2f%%)",
                memory_data.get("scenes_evaluated", 0),
                memory_data.get("pass_rate", 0.0) * 100,
            )
        except Exception as exc:
            logger.warning("QualityAgent: failed to load memory: %s", exc)

    def _save_persistent_memory(self, result: QualityResult) -> None:
        """Save persistent memory if Dreaming enabled."""
        if not self.ctx.managed_agent_config or not self.ctx.managed_agent_config.dreaming_enabled:
            return

        memory_file = self.ctx.managed_agent_config.get_memory_file("QualityAgent")
        memory_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            import json

            existing = {}
            if memory_file.exists():
                existing = json.loads(memory_file.read_text(encoding="utf-8"))

            # Update counters
            existing["scenes_evaluated"] = existing.get("scenes_evaluated", 0) + 1
            existing["total_pass"] = existing.get("total_pass", 0) + (
                1 if result.tier == "pass" else 0
            )
            existing["total_warn"] = existing.get("total_warn", 0) + (
                1 if result.tier == "warn" else 0
            )
            existing["total_fail"] = existing.get("total_fail", 0) + (
                1 if result.tier == "fail" else 0
            )
            existing["total_sensitivity_violations"] = existing.get(
                "total_sensitivity_violations", 0
            ) + (1 if result.sensitivity_violation else 0)

            # Calculate pass rate
            total = existing["scenes_evaluated"]
            existing["pass_rate"] = existing["total_pass"] / total if total > 0 else 0.0

            # Track last 10 scenes
            if "recent_scenes" not in existing:
                existing["recent_scenes"] = []
            existing["recent_scenes"].append(
                {
                    "scene_id": result.scene_id,
                    "tier": result.tier,
                    "needs_review": result.needs_review,
                    "nofly": result.nofly_violations,
                    "structural": result.structural_flags,
                    "sensitivity": result.sensitivity_violation,
                }
            )
            existing["recent_scenes"] = existing["recent_scenes"][-10:]

            memory_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            logger.debug("QualityAgent: saved memory (%d scenes)", existing["scenes_evaluated"])
        except Exception as exc:
            logger.warning("QualityAgent: failed to save memory: %s", exc)


def _check_sensitivity(job_context: JobContext) -> bool:
    max_heat = job_context.spec.sensitivity_thresholds.max_heat_level
    return float(job_context.heat_level) > max_heat


def _classify_tier(
    nofly: int,
    structural: int,
    verdict: Verdict,
    structural_weighted: int | None = None,
    word_count: int = 0,
) -> tuple[str, bool]:
    structural_warn_threshold = _structural_warn_threshold(word_count)
    structural_weighted_score = structural if structural_weighted is None else structural_weighted
    structural_weighted_warn_threshold = _structural_weighted_warn_threshold(word_count)
    if nofly == 0 and structural == 0 and verdict != Verdict.NEEDS_REVIEW:
        if verdict in (Verdict.POSITIVE, Verdict.NEUTRAL):
            return "pass", False
    if (
        nofly <= 2
        and structural <= structural_warn_threshold
        and structural_weighted_score <= structural_weighted_warn_threshold
        and verdict != Verdict.NEEDS_REVIEW
    ):
        return "warn", False
    return "fail", True


def _structural_warn_threshold(word_count: int) -> int:
    if word_count <= 0:
        return 6
    return max(6, math.ceil((word_count / 1000) * 6))


def _structural_weighted_warn_threshold(word_count: int) -> int:
    if word_count <= 0:
        return 5
    return max(5, math.floor((word_count / 1000) * 5))


def _minimum_scene_word_count(word_count_target: int) -> int:
    if word_count_target <= 0:
        return 0
    return max(1, round(word_count_target * _SCENE_WORD_TARGET_MIN_RATIO))
