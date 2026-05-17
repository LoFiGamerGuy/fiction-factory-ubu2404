"""Integration tests for SpecValidatorAgent (Task 010)."""

from __future__ import annotations

from pathlib import Path

import yaml

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
