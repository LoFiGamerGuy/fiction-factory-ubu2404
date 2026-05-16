"""Integration tests — V1 profile library: load, compose, and distinguish pentads."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.profiles.profile_registry import ProfileRegistry
from pipeline.profiles.project_spec import ProjectSpec
from pipeline.profiles.spec_loader import SpecLoader

WORKSPACE_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture
def loader() -> SpecLoader:
    return SpecLoader(workspace_root=WORKSPACE_ROOT)


@pytest.fixture
def registry() -> ProfileRegistry:
    return ProfileRegistry(workspace_root=WORKSPACE_ROOT)


# ── Individual profile validation ─────────────────────────────────────────────


class TestProfileLibraryValidation:
    def test_author_default_loads(self, loader: SpecLoader) -> None:
        p = loader.load("author", "default")
        assert p["profile_id"] == "author_default_placeholder"
        assert p["version"] == "0.1"
        assert "voice_axes" in p

    def test_romance_module_v1_loads(self, loader: SpecLoader) -> None:
        p = loader.load("genre", "romance_module_v1")
        assert p["genre_name"] == "romance"
        assert p["genre_module_status"] == "validated"

    def test_erotica_module_v1_loads(self, loader: SpecLoader) -> None:
        p = loader.load("genre", "erotica_module_v1")
        assert p["genre_name"] == "erotica"
        assert p["genre_module_status"] == "validated"

    def test_thriller_module_v01_loads(self, loader: SpecLoader) -> None:
        p = loader.load("genre", "thriller_module_v01")
        assert p["genre_module_status"] == "scaffold"

    def test_sensitivity_default_loads(self, loader: SpecLoader) -> None:
        p = loader.load("sensitivity", "default")
        assert p["sacred"] is True
        assert p["content_domain_policies"]["minors_in_sexual_context"] == "prohibit"

    def test_kdp_commercial_loads(self, loader: SpecLoader) -> None:
        p = loader.load("goal", "kdp_commercial")
        assert p["intent"] == "kdp_high_revenue"

    def test_romance_reader_loads(self, loader: SpecLoader) -> None:
        p = loader.load("audience", "romance_reader")
        assert "hea_required" in p["expectation_set"]

    def test_erotica_reader_loads(self, loader: SpecLoader) -> None:
        p = loader.load("audience", "erotica_reader")
        assert "explicit_content_by_chapter_2" in p["expectation_set"]


# ── Romance pentad composition ────────────────────────────────────────────────


class TestRomancePentad:
    @pytest.fixture
    def romance_spec(self, registry: ProfileRegistry) -> ProjectSpec:
        return registry.compose(
            book_id="test-romance-001",
            series_id="test-series-001",
            author_name="default",
            genre_name="romance_module_v1",
            audience_name="romance_reader",
            sensitivity_name="default",
            goal_name="kdp_commercial",
        )

    def test_compose_returns_frozen_spec(self, romance_spec: ProjectSpec) -> None:
        assert isinstance(romance_spec, ProjectSpec)
        assert romance_spec.is_frozen is True

    def test_genre_config_populated(self, romance_spec: ProjectSpec) -> None:
        assert romance_spec.genre_config.genre_name == "romance"
        assert romance_spec.genre_config.genre_module_status == "validated"
        assert "meet_cute" in romance_spec.genre_config.scene_function_vocabulary

    def test_sensitivity_thresholds_present(self, romance_spec: ProjectSpec) -> None:
        assert romance_spec.sensitivity_thresholds.max_heat_level == 5.0
        assert romance_spec.sensitivity_thresholds.max_violence_intensity == 5.0

    def test_goal_intent_kdp(self, romance_spec: ProjectSpec) -> None:
        assert romance_spec.goal_weights.intent == "kdp_high_revenue"

    def test_audience_expectations_present(self, romance_spec: ProjectSpec) -> None:
        assert "hea_required" in romance_spec.audience_expectations.expectation_set

    def test_profile_versions_pinned(self, romance_spec: ProjectSpec) -> None:
        assert romance_spec.profile_versions["genre"] == "1.0"
        assert romance_spec.profile_versions["sensitivity"] == "1.0"

    def test_romance_has_no_interiority_budget(self, romance_spec: ProjectSpec) -> None:
        assert "interiority_budget_pct_max" not in romance_spec.raw_profiles["genre"]


# ── Erotica pentad composition ────────────────────────────────────────────────


class TestEroticaPentad:
    @pytest.fixture
    def erotica_spec(self, registry: ProfileRegistry) -> ProjectSpec:
        return registry.compose(
            book_id="test-erotica-001",
            series_id="test-series-001",
            author_name="default",
            genre_name="erotica_module_v1",
            audience_name="erotica_reader",
            sensitivity_name="default",
            goal_name="kdp_commercial",
        )

    def test_compose_returns_frozen_spec(self, erotica_spec: ProjectSpec) -> None:
        assert isinstance(erotica_spec, ProjectSpec)
        assert erotica_spec.is_frozen is True

    def test_interiority_budget_pct_max(self, erotica_spec: ProjectSpec) -> None:
        assert erotica_spec.raw_profiles["genre"]["interiority_budget_pct_max"] == pytest.approx(
            0.20
        )

    def test_heat_curve_steep(self, erotica_spec: ProjectSpec) -> None:
        assert erotica_spec.raw_profiles["genre"]["heat_curve"] == "steep"

    def test_exposition_budget_pct_max(self, erotica_spec: ProjectSpec) -> None:
        assert erotica_spec.raw_profiles["genre"]["exposition_budget_pct_max"] == pytest.approx(
            0.15
        )

    def test_sex_scene_frequency_min(self, erotica_spec: ProjectSpec) -> None:
        assert erotica_spec.raw_profiles["genre"]["sex_scene_frequency_min"] == "1_per_3_chapters"

    def test_genre_name_erotica(self, erotica_spec: ProjectSpec) -> None:
        assert erotica_spec.genre_config.genre_name == "erotica"

    def test_distinct_from_romance(
        self, registry: ProfileRegistry, erotica_spec: ProjectSpec
    ) -> None:
        romance_spec = registry.compose(
            book_id="cmp-r",
            series_id="s1",
            author_name="default",
            genre_name="romance_module_v1",
            audience_name="romance_reader",
            sensitivity_name="default",
            goal_name="kdp_commercial",
        )
        assert erotica_spec.genre_config.genre_name != romance_spec.genre_config.genre_name
        assert "interiority_budget_pct_max" not in romance_spec.raw_profiles["genre"]
        assert erotica_spec.raw_profiles["genre"]["heat_curve"] == "steep"


# ── Thriller scaffold ─────────────────────────────────────────────────────────


class TestThrillerScaffold:
    def test_thriller_loads_without_error(self, loader: SpecLoader) -> None:
        p = loader.load("genre", "thriller_module_v01")
        assert p is not None

    def test_genre_module_status_scaffold(self, loader: SpecLoader) -> None:
        p = loader.load("genre", "thriller_module_v01")
        assert p["genre_module_status"] == "scaffold"

    def test_quality_gates_empty_for_scaffold(self, loader: SpecLoader) -> None:
        p = loader.load("genre", "thriller_module_v01")
        assert p.get("quality_gates") == []

    def test_required_scene_slots_present(self, loader: SpecLoader) -> None:
        p = loader.load("genre", "thriller_module_v01")
        slot_ids = [s["slot_id"] for s in p.get("required_scene_slots", [])]
        assert "inciting_incident" in slot_ids
        assert "climax" in slot_ids
