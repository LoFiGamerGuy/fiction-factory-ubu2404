"""QualityEvaluator — scores a scene's contribution to running book-level targets.

Key invariant: evaluates contribution to running totals, NOT local absolute values.
Fail-closed: any exception in the evaluator yields QualityDecision.needs_review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Verdict(str, Enum):  # noqa: UP042
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    NEEDS_REVIEW = "needs_review"


@dataclass
class MetricResult:
    metric: str
    current_running: float
    projected_running: float
    target: float
    verdict: Verdict
    note: str = ""


@dataclass
class QualityDecision:
    overall_verdict: Verdict
    metric_results: list[MetricResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return self.overall_verdict == Verdict.NEEDS_REVIEW


def _project_running_average(
    current_running: float,
    current_total_words: int,
    scene_value: float,
    scene_words: int,
) -> float:
    """Compute the word-count-weighted average after adding this scene."""
    total = current_total_words + scene_words
    if total == 0:
        return scene_value
    return (current_running * current_total_words + scene_value * scene_words) / total


class QualityEvaluator:
    """Evaluates a candidate scene's contribution to book-level running targets."""

    RATIO_METRICS = {
        "interiority_pct",
        "dialogue_ratio",
        "exposition_pct",
        "action_pct",
        "heat_curve_position",
    }
    DENSITY_METRICS = {"sensory_density_per_1k", "em_dash_density", "sentence_length_avg"}

    def evaluate_scene_contribution(
        self,
        scene_metrics: dict[str, float],
        running_totals: dict[str, float],
        targets: dict[str, float],
        word_count_remaining: int,
    ) -> QualityDecision:
        """Evaluate how this scene moves running totals toward their targets.

        Parameters
        ----------
        scene_metrics:
            Per-scene metrics for the candidate scene (word_count must be present).
        running_totals:
            Current book-level weighted averages / counts after all committed scenes.
        targets:
            Target values for each metric (from resolved profile pentad).
        word_count_remaining:
            Words remaining in the book after this scene (used for urgency weighting).
        """
        try:
            return self._evaluate(scene_metrics, running_totals, targets, word_count_remaining)
        except Exception:
            logger.exception("QualityEvaluator raised unexpectedly — failing closed.")
            return QualityDecision(overall_verdict=Verdict.NEEDS_REVIEW)

    def _evaluate(
        self,
        scene_metrics: dict[str, float],
        running_totals: dict[str, float],
        targets: dict[str, float],
        word_count_remaining: int,
    ) -> QualityDecision:
        scene_words = int(scene_metrics.get("word_count", 0))
        current_total_words = int(running_totals.get("word_count_total", 0))

        results: list[MetricResult] = []
        negative_count = 0

        for metric, target in targets.items():
            scene_value = scene_metrics.get(metric)
            current_running = running_totals.get(metric, 0.0)
            if scene_value is None:
                continue

            if metric in self.RATIO_METRICS or metric in self.DENSITY_METRICS:
                projected = _project_running_average(
                    current_running, current_total_words, scene_value, scene_words
                )
            else:
                # Cumulative counts (ai_tell_count, etc.)
                projected = current_running + scene_value

            current_dist = abs(current_running - target)
            projected_dist = abs(projected - target)

            if projected_dist < current_dist:
                verdict = Verdict.POSITIVE
                note = f"moving toward target (projected={projected:.3f}, target={target:.3f})"
            elif projected_dist > current_dist:
                verdict = Verdict.NEGATIVE
                note = f"moving away from target (projected={projected:.3f}, target={target:.3f})"
                negative_count += 1
            else:
                verdict = Verdict.NEUTRAL
                note = f"no change (projected={projected:.3f})"

            results.append(
                MetricResult(
                    metric=metric,
                    current_running=current_running,
                    projected_running=projected,
                    target=target,
                    verdict=verdict,
                    note=note,
                )
            )

        if not results:
            overall = Verdict.NEUTRAL
        elif negative_count == 0:
            overall = Verdict.POSITIVE
        elif negative_count < len(results) // 2:
            overall = Verdict.NEUTRAL
        else:
            overall = Verdict.NEGATIVE

        return QualityDecision(
            overall_verdict=overall,
            metric_results=results,
            notes=[f"{word_count_remaining} words remaining in book budget."],
        )
