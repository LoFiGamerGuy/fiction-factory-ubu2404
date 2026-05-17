"""Unit tests for BookStructuralVerifier (Task 010)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.book_structural_verifier import (
    BookOutput,
    BookStructuralVerifier,
)
from pipeline.book_structure_planner import BookStructurePlanner, SceneInventory
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)

_ROMANCE_SERIES_SPEC: dict[str, Any] = {
    "series_id": "series_test",
    "genre_config": {
        "genre_name": "romance",
        "heat_curve": "rising",
        "word_count_target": 80000,
        "chapter_count": 20,
        "scene_function_vocabulary": ["meet_cute", "escalation", "resolution"],
        "required_scene_slots": ["meet_cute"],
        "hea_required": True,
    },
}


def _make_spec(genre: str = "romance") -> ProjectSpec:
    return ProjectSpec(
        book_id="book01",
        series_id="series_test",
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(
            genre_name=genre, word_count_min=50000, word_count_max=100000
        ),
        sensitivity_thresholds=ResolvedSensitivityThresholds(),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )


def _make_inventory(tmp_path: Path, spec: dict[str, Any] | None = None) -> SceneInventory:
    planner = BookStructurePlanner()
    return planner.plan(
        book_id="book01",
        series_id="series_test",
        series_spec=spec or _ROMANCE_SERIES_SPEC,
        book_spec={"chapter_count": 20, "scenes_per_chapter": 1, "word_count_target": 80000},
        book_dir=tmp_path / "book01",
    )


class TestWordCountCheck:
    def test_within_tolerance_passes(self, tmp_path: Path) -> None:
        inv = _make_inventory(tmp_path)
        book_output = BookOutput(
            book_id="book01",
            actual_word_count=80000,  # exactly target
            scenes_completed=[
                {
                    "scene_id": s.scene_id,
                    "chapter": s.chapter,
                    "heat_level": s.heat_level_target,
                    "scene_function": s.scene_function,
                }
                for s in inv.scenes
            ],
        )
        spec = _make_spec()
        verifier = BookStructuralVerifier()
        report = verifier.verify(book_output, spec, inv, _ROMANCE_SERIES_SPEC["genre_config"])
        word_failures = [f for f in report.failed_checks if f.check_name == "word_count"]
        assert len(word_failures) == 0

    def test_too_short_fails(self, tmp_path: Path) -> None:
        inv = _make_inventory(tmp_path)
        book_output = BookOutput(
            book_id="book01",
            actual_word_count=10000,  # way too short
            scenes_completed=[],
        )
        spec = _make_spec()
        verifier = BookStructuralVerifier()
        report = verifier.verify(book_output, spec, inv, _ROMANCE_SERIES_SPEC["genre_config"])
        word_failures = [f for f in report.failed_checks if f.check_name == "word_count"]
        assert len(word_failures) == 1


class TestHeatCurveViolation:
    def test_heat_violation_detected(self, tmp_path: Path) -> None:
        inv = _make_inventory(tmp_path)
        # Set all scenes to heat_level=1 (violates rising curve for later scenes)
        scenes_completed = [
            {
                "scene_id": s.scene_id,
                "chapter": s.chapter,
                "heat_level": 1,
                "scene_function": s.scene_function,
            }
            for s in inv.scenes
        ]
        book_output = BookOutput(
            book_id="book01",
            actual_word_count=80000,
            scenes_completed=scenes_completed,
        )
        spec = _make_spec()
        verifier = BookStructuralVerifier()
        report = verifier.verify(book_output, spec, inv, _ROMANCE_SERIES_SPEC["genre_config"])
        heat_failures = [f for f in report.failed_checks if f.check_name == "heat_curve"]
        # At least some late scenes should have heat violations
        assert len(heat_failures) > 0

    def test_correct_heat_passes(self, tmp_path: Path) -> None:
        inv = _make_inventory(tmp_path)
        scenes_completed = [
            {
                "scene_id": s.scene_id,
                "chapter": s.chapter,
                "heat_level": s.heat_level_target,
                "scene_function": s.scene_function,
            }
            for s in inv.scenes
        ]
        book_output = BookOutput(
            book_id="book01",
            actual_word_count=80000,
            scenes_completed=scenes_completed,
        )
        spec = _make_spec()
        verifier = BookStructuralVerifier()
        report = verifier.verify(book_output, spec, inv, _ROMANCE_SERIES_SPEC["genre_config"])
        heat_failures = [f for f in report.failed_checks if f.check_name == "heat_curve"]
        assert len(heat_failures) == 0


class TestHEAHFNCheck:
    def test_missing_hea_hfn_fails(self, tmp_path: Path) -> None:
        planner = BookStructurePlanner()
        # Build inventory where no scene gets HEA/HFN slot
        series_spec_no_hea: dict[str, Any] = {
            "series_id": "series_test",
            "genre_config": {
                "genre_name": "romance",
                "heat_curve": "rising",
                "word_count_target": 40000,
                "chapter_count": 10,
                "scene_function_vocabulary": ["meet_cute", "escalation"],
                "hea_required": True,
            },
        }
        inv = planner.plan(
            book_id="book01",
            series_id="series_test",
            series_spec=series_spec_no_hea,
            book_spec={"chapter_count": 10, "scenes_per_chapter": 1, "word_count_target": 40000},
            book_dir=tmp_path / "book01",
        )
        # Override last scenes to not have HEA function
        for slot in inv.scenes:
            slot.scene_function = "escalation"
            slot.required_slot_id = None

        book_output = BookOutput(
            book_id="book01",
            actual_word_count=40000,
            scenes_completed=[
                {
                    "scene_id": s.scene_id,
                    "chapter": s.chapter,
                    "heat_level": s.heat_level_target,
                    "scene_function": "escalation",
                }
                for s in inv.scenes
            ],
        )
        spec = _make_spec("romance")
        verifier = BookStructuralVerifier()
        report = verifier.verify(book_output, spec, inv, series_spec_no_hea["genre_config"])
        hea_failures = [f for f in report.failed_checks if f.check_name == "hea_hfn"]
        assert len(hea_failures) >= 1


class TestEroticaSexSceneFrequency:
    def test_too_few_sex_scenes_fails(self, tmp_path: Path) -> None:
        planner = BookStructurePlanner()
        erotica_spec: dict[str, Any] = {
            "series_id": "series_test",
            "genre_config": {
                "genre_name": "erotica",
                "heat_curve": "flat",
                "word_count_target": 40000,
                "chapter_count": 10,
                "sex_scene_frequency_min": 0.33,
            },
        }
        inv = planner.plan(
            book_id="book01",
            series_id="series_test",
            series_spec=erotica_spec,
            book_spec={"chapter_count": 10, "scenes_per_chapter": 3, "word_count_target": 40000},
            book_dir=tmp_path / "book01",
        )
        # Only 1 sex scene (well below 0.33 threshold)
        scenes_completed = [
            {
                "scene_id": s.scene_id,
                "chapter": s.chapter,
                "heat_level": s.heat_level_target,
                "scene_function": "dialogue",
            }
            for s in inv.scenes
        ]
        scenes_completed[0]["scene_function"] = "sex_scene"

        book_output = BookOutput(
            book_id="book01",
            actual_word_count=40000,
            scenes_completed=scenes_completed,
        )
        spec = _make_spec("erotica")
        verifier = BookStructuralVerifier()
        report = verifier.verify(book_output, spec, inv, erotica_spec["genre_config"])
        freq_failures = [f for f in report.failed_checks if f.check_name == "sex_scene_frequency"]
        assert len(freq_failures) == 1
