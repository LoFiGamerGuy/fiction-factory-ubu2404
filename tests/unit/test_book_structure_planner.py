"""Unit tests for BookStructurePlanner (Task 010)."""

from __future__ import annotations

from pathlib import Path

from pipeline.book_structure_planner import (
    _DEFAULT_HEAT_CURVES,
    BookStructurePlanner,
    _interpolate_heat,
)

_ROMANCE_SERIES_SPEC = {
    "series_id": "series_test",
    "genre_config": {
        "genre_name": "romance",
        "heat_curve": "rising",
        "word_count_target": 80000,
        "chapter_count": 30,
        "scene_function_vocabulary": [
            "meet_cute",
            "escalation",
            "conflict",
            "black_moment",
            "resolution",
        ],
        "required_scene_slots": ["meet_cute", "black_moment"],
    },
}

_BOOK_SPEC_SIMPLE = {"chapter_count": 10, "scenes_per_chapter": 2, "word_count_target": 40000}


class TestHeatInterpolation:
    def test_rising_curve_start_low(self) -> None:
        waypoints = _DEFAULT_HEAT_CURVES["rising"]
        heat = _interpolate_heat(0.0, waypoints)
        assert heat == 1

    def test_rising_curve_end_high(self) -> None:
        waypoints = _DEFAULT_HEAT_CURVES["rising"]
        heat = _interpolate_heat(1.0, waypoints)
        assert heat == 5

    def test_rising_curve_midpoint(self) -> None:
        waypoints = _DEFAULT_HEAT_CURVES["rising"]
        # At position 0.3, waypoint is (0.3, 2)
        heat = _interpolate_heat(0.3, waypoints)
        assert heat == 2

    def test_flat_curve_constant(self) -> None:
        waypoints = _DEFAULT_HEAT_CURVES["flat"]
        for pos in [0.0, 0.25, 0.5, 0.75, 1.0]:
            heat = _interpolate_heat(pos, waypoints)
            assert heat == 3


class TestBookStructurePlannerSceneCount:
    def test_correct_scene_count(self, tmp_path: Path) -> None:
        planner = BookStructurePlanner()
        inv = planner.plan(
            book_id="book01",
            series_id="series_test",
            series_spec=_ROMANCE_SERIES_SPEC,
            book_spec=_BOOK_SPEC_SIMPLE,
            book_dir=tmp_path / "book01",
        )
        assert inv.total_scenes == 20  # 10 chapters × 2 scenes
        assert len(inv.scenes) == 20

    def test_scene_ids_formatted(self, tmp_path: Path) -> None:
        planner = BookStructurePlanner()
        inv = planner.plan(
            book_id="book01",
            series_id="series_test",
            series_spec=_ROMANCE_SERIES_SPEC,
            book_spec=_BOOK_SPEC_SIMPLE,
            book_dir=tmp_path / "book01",
        )
        first = inv.scenes[0]
        assert first.scene_id == "ch01_sc01"
        assert first.chapter == 1
        assert first.scene_number == 1

    def test_inventory_written_to_disk(self, tmp_path: Path) -> None:
        planner = BookStructurePlanner()
        planner.plan(
            book_id="book01",
            series_id="series_test",
            series_spec=_ROMANCE_SERIES_SPEC,
            book_spec=_BOOK_SPEC_SIMPLE,
            book_dir=tmp_path / "book01",
        )
        assert (tmp_path / "book01" / "scene_inventory.json").exists()


class TestHeatLevelsInterpolated:
    def test_first_scene_low_heat(self, tmp_path: Path) -> None:
        planner = BookStructurePlanner()
        inv = planner.plan(
            book_id="book01",
            series_id="series_test",
            series_spec=_ROMANCE_SERIES_SPEC,
            book_spec=_BOOK_SPEC_SIMPLE,
            book_dir=tmp_path / "book01",
        )
        assert inv.scenes[0].heat_level_target <= 2  # rising curve starts at 1

    def test_last_scene_high_heat(self, tmp_path: Path) -> None:
        planner = BookStructurePlanner()
        inv = planner.plan(
            book_id="book01",
            series_id="series_test",
            series_spec=_ROMANCE_SERIES_SPEC,
            book_spec=_BOOK_SPEC_SIMPLE,
            book_dir=tmp_path / "book01",
        )
        assert inv.scenes[-1].heat_level_target >= 4  # rising curve ends at 5

    def test_act_assignments(self, tmp_path: Path) -> None:
        planner = BookStructurePlanner()
        inv = planner.plan(
            book_id="book01",
            series_id="series_test",
            series_spec=_ROMANCE_SERIES_SPEC,
            book_spec=_BOOK_SPEC_SIMPLE,
            book_dir=tmp_path / "book01",
        )
        acts = {s.act for s in inv.scenes}
        assert 1 in acts and 2 in acts and 3 in acts
