"""GenreNormEditorAgent — enforces genre module requirements on a scene.

Reads genre_profile.yaml via SpecLoader for:
  - scene_function vocabulary
  - heat_curve compliance
  - required_scene_slots fulfillment

Runs on every scene (unlike other specialist agents which run selectively).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from pipeline.core.base_agent import BaseAgent
from pipeline.core.job_context import JobContext

if TYPE_CHECKING:
    from pipeline.core.agent_context import AgentContext

logger = logging.getLogger(__name__)

# ── Result dataclasses ────────────────────────────────────────────────────────


@dataclass
class SlotViolation:
    violation_type: str  # "invalid_scene_function" | "heat_curve" | "required_slot_missing"
    expected: str
    actual: str
    scene_id: str
    severity: str = "high"


@dataclass
class GenreNormResult:
    scene_id: str
    passed: bool
    violations: list[SlotViolation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ── Agent ─────────────────────────────────────────────────────────────────────


class GenreNormEditorAgent(BaseAgent):
    """Deterministic genre compliance checker; reads genre profile at init."""

    impl_class: ClassVar[str] = "deterministic"
    version: ClassVar[str] = "1.0"

    def __init__(self, ctx: AgentContext) -> None:
        super().__init__(ctx)
        self._genre_profile: dict[str, Any] = self._load_genre_profile(ctx)

    @staticmethod
    def _load_genre_profile(ctx: AgentContext) -> dict[str, Any]:
        try:
            spec_loader = ctx.spec_loader
            genre_name = "romance_module_v1"
            return spec_loader.load("genre", genre_name)
        except Exception as exc:
            logger.warning("GenreNormEditorAgent: could not load genre profile: %s", exc)
            return {}

    def _execute(self, job_context: JobContext) -> JobContext:
        scene_function = job_context.output_data.get("_scene_function", "")
        heat_level = job_context.heat_level
        book_position = self._estimate_book_position(job_context)

        result = GenreNormResult(scene_id=job_context.scene_id, passed=True)

        self.enforce_scene_function(scene_function, result)
        self.enforce_heat_curve(heat_level, book_position, result)

        if result.violations:
            result.passed = False

        logger.info(
            "GenreNormEditorAgent: scene=%s passed=%s violations=%d",
            job_context.scene_id,
            result.passed,
            len(result.violations),
        )

        return job_context.with_output(
            "genre_norm_editor_agent",
            {
                "scene_id": result.scene_id,
                "passed": result.passed,
                "violations": [
                    {
                        "violation_type": v.violation_type,
                        "expected": v.expected,
                        "actual": v.actual,
                        "scene_id": v.scene_id,
                        "severity": v.severity,
                    }
                    for v in result.violations
                ],
                "notes": result.notes,
            },
        )

    def enforce_scene_function(self, scene_function: str, result: GenreNormResult) -> None:
        vocabulary = self._genre_profile.get("scene_function_vocabulary", [])
        if not vocabulary or not scene_function:
            return
        if scene_function not in vocabulary:
            result.violations.append(
                SlotViolation(
                    violation_type="invalid_scene_function",
                    expected=f"one of {vocabulary[:5]}...",
                    actual=scene_function,
                    scene_id=result.scene_id,
                )
            )

    def enforce_heat_curve(
        self,
        heat_level: int,
        book_position: float,
        result: GenreNormResult,
    ) -> bool:
        """Check heat_level against heat_curve target for current book position.

        Returns True if compliant, False if violation (also appends to result).
        """
        heat_curve = self._genre_profile.get("heat_curve", "")
        if not heat_curve:
            return True

        expected_max = self._heat_ceiling_for_position(heat_curve, book_position)
        if heat_level > expected_max:
            result.violations.append(
                SlotViolation(
                    violation_type="heat_curve",
                    expected=f"heat_level ≤ {expected_max} at position {book_position:.2f}",
                    actual=str(heat_level),
                    scene_id=result.scene_id,
                )
            )
            return False
        return True

    def check_required_slots(
        self,
        chapter_scenes: list[dict[str, Any]],
    ) -> list[SlotViolation]:
        """Check required_scene_slots fulfillment for a chapter."""
        required_slots = self._genre_profile.get("required_scene_slots", [])
        if not required_slots:
            return []

        fulfilled_functions = {s.get("scene_function", "") for s in chapter_scenes}
        violations: list[SlotViolation] = []
        for slot in required_slots:
            slot_id = slot.get("slot_id", "")
            scene_func = slot.get("scene_function", "")
            if scene_func and scene_func not in fulfilled_functions:
                violations.append(
                    SlotViolation(
                        violation_type="required_slot_missing",
                        expected=f"scene_function={scene_func} (slot={slot_id})",
                        actual="not fulfilled",
                        scene_id="chapter-level",
                    )
                )
        return violations

    @staticmethod
    def _heat_ceiling_for_position(heat_curve: str, position: float) -> int:
        """Interpolate maximum allowed heat_level from heat_curve type and position."""
        # For Romance "rising" curve: early chapters low heat, late chapters high
        curves: dict[str, list[tuple[float, int]]] = {
            "rising": [(0.0, 2), (0.3, 3), (0.6, 4), (1.0, 5)],
            "steep": [(0.0, 3), (0.2, 4), (0.4, 5), (1.0, 5)],
            "plateau": [(0.0, 3), (0.5, 4), (1.0, 4)],
            "flat": [(0.0, 3), (1.0, 3)],
        }
        curve_points = curves.get(heat_curve, curves["flat"])
        # Linear interpolation
        for i in range(len(curve_points) - 1):
            x0, y0 = curve_points[i]
            x1, y1 = curve_points[i + 1]
            if x0 <= position <= x1:
                t = (position - x0) / (x1 - x0) if x1 > x0 else 0.0
                return int(y0 + t * (y1 - y0))
        return int(curve_points[-1][1])

    @staticmethod
    def _estimate_book_position(job_context: JobContext) -> float:
        chapter_count_max = job_context.spec.genre_config.chapter_count_max or 30
        return min(1.0, job_context.chapter_id / chapter_count_max)
