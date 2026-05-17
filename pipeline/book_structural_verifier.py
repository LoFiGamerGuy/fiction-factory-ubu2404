"""BookStructuralVerifier — post-generation structural compliance checks.

Checks: word count, act proportions, scene count, heat curve compliance,
genre-specific checks (HEA/HFN for Romance, sex scene frequency for Erotica),
and RTM required_scene_slots coverage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pipeline.book_structure_planner import _DEFAULT_HEAT_CURVES, SceneInventory, _interpolate_heat
from pipeline.profiles.project_spec import ProjectSpec

logger = logging.getLogger(__name__)

_ACT_PROPORTIONS = {"act1": 0.25, "act2": 0.50, "act3": 0.25}
_ACT_TOLERANCE = 0.05  # ±5 percentage points
_WORD_COUNT_TOLERANCE = 0.10  # ±10%
_HEAT_TOLERANCE = 1  # ±1 heat level per chapter


@dataclass
class FailedCheck:
    check_name: str
    description: str


@dataclass
class VerificationReport:
    passed: bool
    failed_checks: list[FailedCheck] = field(default_factory=list)


@dataclass
class BookOutput:
    """Aggregated book-level output for verification."""

    book_id: str
    actual_word_count: int
    scenes_completed: list[dict[str, Any]]  # each: {scene_id, chapter, heat_level, scene_function}


class BookStructuralVerifier:
    """Verifies a completed book against its spec and scene inventory."""

    def verify(
        self,
        book_output: BookOutput,
        spec: ProjectSpec,
        inventory: SceneInventory,
        genre_spec: dict[str, Any] | None = None,
    ) -> VerificationReport:
        failures: list[FailedCheck] = []

        self._check_word_count(book_output, spec, inventory, failures)
        self._check_act_proportions(book_output, inventory, failures)
        self._check_scene_count(book_output, inventory, failures)
        self._check_heat_curve(book_output, spec, inventory, genre_spec, failures)
        self._check_genre_specific(book_output, spec, inventory, genre_spec, failures)
        self._check_rtm_requirements(book_output, spec, inventory, genre_spec, failures)

        passed = len(failures) == 0
        report = VerificationReport(passed=passed, failed_checks=failures)
        logger.info(
            "BookStructuralVerifier: book=%s passed=%s checks_failed=%d",
            book_output.book_id,
            passed,
            len(failures),
        )
        return report

    # ── Individual checks ─────────────────────────────────────────────────────

    def _check_word_count(
        self,
        book_output: BookOutput,
        spec: ProjectSpec,
        inventory: SceneInventory,
        failures: list[FailedCheck],
    ) -> None:
        target = inventory.word_count_target
        actual = book_output.actual_word_count
        lo = target * (1 - _WORD_COUNT_TOLERANCE)
        hi = target * (1 + _WORD_COUNT_TOLERANCE)
        if not (lo <= actual <= hi):
            failures.append(
                FailedCheck(
                    check_name="word_count",
                    description=(
                        f"Word count {actual} outside tolerance "
                        f"[{int(lo)}–{int(hi)}] (target={target})."
                    ),
                )
            )

    def _check_act_proportions(
        self,
        book_output: BookOutput,
        inventory: SceneInventory,
        failures: list[FailedCheck],
    ) -> None:
        total = len(book_output.scenes_completed)
        if total == 0:
            return
        act_counts: dict[int, int] = {1: 0, 2: 0, 3: 0}
        for slot in inventory.scenes:
            act_counts[slot.act] = act_counts.get(slot.act, 0) + 1
        for act_num, expected_frac in [
            (1, _ACT_PROPORTIONS["act1"]),
            (2, _ACT_PROPORTIONS["act2"]),
            (3, _ACT_PROPORTIONS["act3"]),
        ]:
            actual_frac = act_counts.get(act_num, 0) / total
            if abs(actual_frac - expected_frac) > _ACT_TOLERANCE:
                failures.append(
                    FailedCheck(
                        check_name=f"act{act_num}_proportion",
                        description=(
                            f"Act {act_num} proportion {actual_frac:.1%} deviates from "
                            f"target {expected_frac:.1%} by more than {_ACT_TOLERANCE:.0%}."
                        ),
                    )
                )

    def _check_scene_count(
        self,
        book_output: BookOutput,
        inventory: SceneInventory,
        failures: list[FailedCheck],
    ) -> None:
        expected = inventory.total_scenes
        actual = len(book_output.scenes_completed)
        if actual != expected:
            failures.append(
                FailedCheck(
                    check_name="scene_count",
                    description=f"Scene count {actual} ≠ inventory target {expected}.",
                )
            )

    def _check_heat_curve(
        self,
        book_output: BookOutput,
        spec: ProjectSpec,
        inventory: SceneInventory,
        genre_spec: dict[str, Any] | None,
        failures: list[FailedCheck],
    ) -> None:
        gs = genre_spec or {}
        heat_curve_name = gs.get("heat_curve", "rising")
        heat_waypoints = _DEFAULT_HEAT_CURVES.get(heat_curve_name, _DEFAULT_HEAT_CURVES["rising"])
        raw_wp = gs.get("heat_curve_waypoints")
        if raw_wp and isinstance(raw_wp, list):
            heat_waypoints = [(float(p), int(h)) for p, h in raw_wp]

        completed = {s["scene_id"]: s for s in book_output.scenes_completed}
        slot_by_id = {s.scene_id: s for s in inventory.scenes}

        for scene_id, slot in slot_by_id.items():
            scene_data = completed.get(scene_id)
            if scene_data is None:
                continue
            actual_heat = int(scene_data.get("heat_level", 0))
            target_heat = _interpolate_heat(slot.position, heat_waypoints)
            if abs(actual_heat - target_heat) > _HEAT_TOLERANCE:
                failures.append(
                    FailedCheck(
                        check_name="heat_curve",
                        description=(
                            f"Scene {scene_id} heat_level={actual_heat} deviates from "
                            f"target={target_heat} by more than {_HEAT_TOLERANCE}."
                        ),
                    )
                )

    def _check_genre_specific(
        self,
        book_output: BookOutput,
        spec: ProjectSpec,
        inventory: SceneInventory,
        genre_spec: dict[str, Any] | None,
        failures: list[FailedCheck],
    ) -> None:
        genre = spec.genre_config.genre_name.lower()
        gs = genre_spec or {}

        # Romance: HEA/HFN required in last 5% of scenes
        if "romance" in genre:
            hea_required = gs.get("hea_required", True)
            if hea_required:
                cutoff = max(1, int(inventory.total_scenes * 0.95))
                last_scenes = inventory.scenes[cutoff:]
                hea_found = any(
                    s.required_slot_id in ("HEA", "HFN", "HEA_or_HFN")
                    or s.scene_function in ("hea", "hfn", "resolution")
                    for s in last_scenes
                )
                if not hea_found:
                    failures.append(
                        FailedCheck(
                            check_name="hea_hfn",
                            description=(
                                "Romance module: no HEA/HFN scene found in last 5% of the book."
                            ),
                        )
                    )

        # Erotica: sex scene frequency check
        if "erotica" in genre:
            min_freq = float(gs.get("sex_scene_frequency_min", 0.33))
            sex_count = sum(
                1
                for s in book_output.scenes_completed
                if s.get("scene_function", "") in ("sex_scene", "erotic_encounter", "intimacy")
            )
            actual_freq = sex_count / max(1, inventory.total_scenes // 3)
            if actual_freq < min_freq:
                failures.append(
                    FailedCheck(
                        check_name="sex_scene_frequency",
                        description=(
                            f"Erotica module: sex scene frequency {actual_freq:.2f} "
                            f"below minimum {min_freq:.2f}."
                        ),
                    )
                )

    def _check_rtm_requirements(
        self,
        book_output: BookOutput,
        spec: ProjectSpec,
        inventory: SceneInventory,
        genre_spec: dict[str, Any] | None,
        failures: list[FailedCheck],
    ) -> None:
        gs = genre_spec or {}
        required_slots: list[str] = list(gs.get("required_scene_slots", []))
        if not required_slots:
            return

        filled_slots = {
            s.required_slot_id for s in inventory.scenes if s.required_slot_id is not None
        }
        for slot_id in required_slots:
            if slot_id not in filled_slots:
                failures.append(
                    FailedCheck(
                        check_name="rtm_required_slot",
                        description=(
                            f"Required scene slot '{slot_id}' not fulfilled in SceneInventory."
                        ),
                    )
                )
