"""Integration tests for SpecValidatorAgent (Task 010)."""

from __future__ import annotations

from pathlib import Path

import yaml

from pipeline.book_structure_planner import BookStructurePlanner
from pipeline.spec_loader import SeriesSpecLoader
from pipeline.spec_validator_agent import SpecValidatorAgent

_VALID_SPEC = {
    "series_id": "test_series",
    "genre_config": {
        "genre_name": "romance",
        "heat_curve": "rising",
        "word_count_target": 80000,
    },
}

_SENTINEL = "REQUIRED — fill in"


class TestSpecValidatorSentinel:
    def test_sentinel_string_rejected(self, tmp_path: Path) -> None:
        spec_path = tmp_path / "spec.yaml"
        spec_path.write_text(
            yaml.dump({**_VALID_SPEC, "word_count_target": _SENTINEL}),
            encoding="utf-8",
        )
        agent = SpecValidatorAgent()
        result = agent.validate(spec_path)
        assert not result.valid
        assert any("Sentinel" in e or "REQUIRED" in e for e in result.errors)

    def test_nested_sentinel_rejected(self, tmp_path: Path) -> None:
        spec_path = tmp_path / "spec.yaml"
        nested = {
            "series_id": "test_series",
            "genre_config": {"genre_name": _SENTINEL},
        }
        spec_path.write_text(yaml.dump(nested), encoding="utf-8")
        agent = SpecValidatorAgent()
        result = agent.validate(spec_path)
        assert not result.valid


class TestSpecValidatorValid:
    def test_valid_spec_passes(self, tmp_path: Path) -> None:
        spec_path = tmp_path / "spec.yaml"
        spec_path.write_text(yaml.dump(_VALID_SPEC), encoding="utf-8")
        agent = SpecValidatorAgent()
        result = agent.validate(spec_path)
        assert result.valid
        assert result.errors == []

    def test_cedar_harbor_production_scaffold_validates_and_plans(self, tmp_path: Path) -> None:
        series_spec_path = Path("data/series/cedar-harbor-romance/spec.yaml")
        book_spec_path = Path("data/series/cedar-harbor-romance/data/books/book01/spec.yaml")

        agent = SpecValidatorAgent()
        result = agent.validate(series_spec_path)
        assert result.valid
        assert result.errors == []

        loader = SeriesSpecLoader()
        series_spec = loader.load(series_spec_path)
        book_spec = loader.load(book_spec_path)
        inventory = BookStructurePlanner().plan(
            book_id="book01",
            series_id="cedar-harbor-romance",
            series_spec=series_spec,
            book_spec=book_spec,
            book_dir=tmp_path / "book01",
        )

        assert inventory.total_scenes == 50
        assert inventory.word_count_target == 65000
        assert all(scene.scene_brief for scene in inventory.scenes)
        required_slots = {scene.required_slot_id for scene in inventory.scenes}
        assert "meet_cute" in required_slots
        assert "inciting_romantic_conflict" in required_slots
        assert "midpoint_emotional_peak" in required_slots
        assert "black_moment" in required_slots
        assert "grand_gesture" in required_slots
        assert inventory.scenes[-1].required_slot_id == "HEA_or_HFN"


class TestSpecValidatorMissingKey:
    def test_missing_required_key_rejected(self, tmp_path: Path) -> None:
        spec_path = tmp_path / "spec.yaml"
        # Missing genre_config
        spec_path.write_text(
            yaml.dump({"series_id": "test_series"}),
            encoding="utf-8",
        )
        agent = SpecValidatorAgent()
        result = agent.validate(spec_path)
        assert not result.valid
        assert any("genre_config" in e for e in result.errors)

    def test_missing_file_rejected(self, tmp_path: Path) -> None:
        agent = SpecValidatorAgent()
        result = agent.validate(tmp_path / "nonexistent.yaml")
        assert not result.valid
