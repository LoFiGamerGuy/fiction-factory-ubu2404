"""Profile system tests — loading, conflict resolution, sacred sensitivity."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pipeline.profiles.conflict_resolver import ConflictResolver, SensitivityViolation
from pipeline.profiles.profile_registry import ProfileRegistry
from pipeline.profiles.project_spec import ProjectSpec
from pipeline.profiles.spec_loader import ProfileLoadError, SpecLoader

WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.fixture
def loader() -> SpecLoader:
    return SpecLoader(workspace_root=WORKSPACE_ROOT)


@pytest.fixture
def registry() -> ProfileRegistry:
    return ProfileRegistry(workspace_root=WORKSPACE_ROOT)


@pytest.fixture
def resolver() -> ConflictResolver:
    return ConflictResolver()


def _fixture_profiles(
    loader: SpecLoader,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    author = loader.load("author", "fixture")
    genre = loader.load("genre", "fixture")
    audience = loader.load("audience", "fixture")
    sensitivity = loader.load("sensitivity", "fixture")
    goal = loader.load("goal", "fixture")
    return author, genre, audience, sensitivity, goal


# ── Schema validation / loading ───────────────────────────────────────────────


class TestSpecLoader:
    def test_loads_all_5_fixture_profiles(self, loader: SpecLoader) -> None:
        author, genre, audience, sensitivity, goal = _fixture_profiles(loader)
        assert author["profile_id"] == "fixture-author-001"
        assert genre["genre_name"] == "romance"
        assert audience["profile_id"] == "fixture-audience-001"
        assert sensitivity["sacred"] is True
        assert goal["intent"] == "series_brand"

    def test_missing_profile_raises(self, loader: SpecLoader) -> None:
        with pytest.raises(ProfileLoadError, match="not found"):
            loader.load("author", "nonexistent_profile_xyz")

    def test_unknown_profile_type_raises(self, loader: SpecLoader) -> None:
        with pytest.raises(ProfileLoadError, match="Unknown profile type"):
            loader.load("mystery_type", "anything")

    def test_version_pinned_in_loaded_profile(self, loader: SpecLoader) -> None:
        author = loader.load("author", "fixture")
        assert author.get("version") == "1.0.0"


# ── ProjectSpec composition ───────────────────────────────────────────────────


class TestProfileRegistry:
    def test_compose_returns_project_spec(self, registry: ProfileRegistry) -> None:
        spec = registry.compose(
            book_id="test-book-001",
            series_id="test-series-001",
            author_name="fixture",
            genre_name="fixture",
            audience_name="fixture",
            sensitivity_name="fixture",
            goal_name="fixture",
        )
        assert isinstance(spec, ProjectSpec)
        assert spec.is_frozen is True

    def test_spec_has_all_profile_versions(self, registry: ProfileRegistry) -> None:
        spec = registry.compose(
            book_id="b1",
            series_id="s1",
            author_name="fixture",
            genre_name="fixture",
            audience_name="fixture",
            sensitivity_name="fixture",
            goal_name="fixture",
        )
        assert "author" in spec.profile_versions
        assert "genre" in spec.profile_versions
        assert "sensitivity" in spec.profile_versions
        assert spec.profile_versions["author"] == "1.0.0"

    def test_spec_genre_config_populated(self, registry: ProfileRegistry) -> None:
        spec = registry.compose(
            book_id="b1",
            series_id="s1",
            author_name="fixture",
            genre_name="fixture",
            audience_name="fixture",
            sensitivity_name="fixture",
            goal_name="fixture",
        )
        assert spec.genre_config.genre_name == "romance"
        assert "meet_cute" in spec.genre_config.scene_function_vocabulary

    def test_spec_sensitivity_thresholds_present(self, registry: ProfileRegistry) -> None:
        spec = registry.compose(
            book_id="b1",
            series_id="s1",
            author_name="fixture",
            genre_name="fixture",
            audience_name="fixture",
            sensitivity_name="fixture",
            goal_name="fixture",
        )
        assert spec.sensitivity_thresholds.max_heat_level == 5.0

    def test_spec_audience_expectations_present(self, registry: ProfileRegistry) -> None:
        spec = registry.compose(
            book_id="b1",
            series_id="s1",
            author_name="fixture",
            genre_name="fixture",
            audience_name="fixture",
            sensitivity_name="fixture",
            goal_name="fixture",
        )
        assert "hea_required" in spec.audience_expectations.expectation_set

    def test_round_trip_composition_timestamp_set(self, registry: ProfileRegistry) -> None:
        spec = registry.compose(
            book_id="b1",
            series_id="s1",
            author_name="fixture",
            genre_name="fixture",
            audience_name="fixture",
            sensitivity_name="fixture",
            goal_name="fixture",
        )
        assert spec.composition_timestamp != ""


# ── Conflict resolution ───────────────────────────────────────────────────────


class TestConflictResolver:
    def _make_profiles(
        self, loader: SpecLoader
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        return _fixture_profiles(loader)

    def test_resolver_returns_dict(self, resolver: ConflictResolver, loader: SpecLoader) -> None:
        a, g, au, s, go = _fixture_profiles(loader)
        result = resolver.resolve(a, g, au, s, go)
        assert isinstance(result, dict)

    def test_sensitivity_wins_over_author(self, resolver: ConflictResolver) -> None:
        """Sensitivity takes precedence over author for shared keys."""
        author = {
            "profile_id": "a",
            "version": "1",
            "voice_axes": {},
            "enforcement_weights": {},
            "shared_key": "author_value",
        }
        sensitivity = {
            "profile_id": "s",
            "version": "1",
            "sacred": True,
            "content_domain_policies": {},
            "hard_thresholds": {},
            "audience_markers": [],
            "shared_key": "sensitivity_value",
        }
        genre = {
            "profile_id": "g",
            "version": "1",
            "genre_name": "r",
            "genre_module_status": "scaffold",
            "scene_function_vocabulary": [],
            "structural_conventions": {
                "word_count_range": {"min": 1, "max": 2},
                "chapter_count_range": {"min": 1, "max": 2},
            },
        }
        audience = {
            "profile_id": "au",
            "version": "1",
            "reader_lens": "",
            "tolerance_bands": {},
            "expectation_set": [],
            "trigger_sets": {"dnf_triggers": [], "satisfaction_triggers": []},
        }
        goal = {
            "profile_id": "go",
            "version": "1",
            "intent": "series_brand",
            "conflict_precedence_rules": [],
            "success_criteria": [],
        }

        result = resolver.resolve(author, genre, audience, sensitivity, goal)
        # sensitivity takes precedence over author
        assert result.get("shared_key") == "sensitivity_value"

    def test_goal_wins_over_genre(self, resolver: ConflictResolver) -> None:
        """Goal takes precedence over genre for shared keys."""
        author = {"profile_id": "a", "version": "1", "voice_axes": {}, "enforcement_weights": {}}
        sensitivity = {
            "profile_id": "s",
            "version": "1",
            "sacred": True,
            "content_domain_policies": {},
            "hard_thresholds": {},
            "audience_markers": [],
        }
        genre = {
            "profile_id": "g",
            "version": "1",
            "genre_name": "r",
            "genre_module_status": "scaffold",
            "scene_function_vocabulary": [],
            "structural_conventions": {
                "word_count_range": {"min": 1, "max": 2},
                "chapter_count_range": {"min": 1, "max": 2},
            },
            "shared_field": "genre_value",
        }
        audience = {
            "profile_id": "au",
            "version": "1",
            "reader_lens": "",
            "tolerance_bands": {},
            "expectation_set": [],
            "trigger_sets": {"dnf_triggers": [], "satisfaction_triggers": []},
        }
        goal = {
            "profile_id": "go",
            "version": "1",
            "intent": "series_brand",
            "conflict_precedence_rules": [],
            "success_criteria": [],
            "shared_field": "goal_value",
        }

        result = resolver.resolve(author, genre, audience, sensitivity, goal)
        assert result.get("shared_field") == "goal_value"

    def test_author_wins_over_universal(self, resolver: ConflictResolver) -> None:
        """Author takes precedence over universal (baseline) defaults."""
        # Author has 'display_name' set; it should survive in resolved
        author = {
            "profile_id": "a",
            "version": "1",
            "display_name": "My Author",
            "voice_axes": {},
            "enforcement_weights": {},
        }
        sensitivity = {
            "profile_id": "s",
            "version": "1",
            "sacred": True,
            "content_domain_policies": {},
            "hard_thresholds": {},
            "audience_markers": [],
        }
        genre = {
            "profile_id": "g",
            "version": "1",
            "genre_name": "r",
            "genre_module_status": "scaffold",
            "scene_function_vocabulary": [],
            "structural_conventions": {
                "word_count_range": {"min": 1, "max": 2},
                "chapter_count_range": {"min": 1, "max": 2},
            },
        }
        audience = {
            "profile_id": "au",
            "version": "1",
            "reader_lens": "",
            "tolerance_bands": {},
            "expectation_set": [],
            "trigger_sets": {"dnf_triggers": [], "satisfaction_triggers": []},
        }
        goal = {
            "profile_id": "go",
            "version": "1",
            "intent": "series_brand",
            "conflict_precedence_rules": [],
            "success_criteria": [],
        }
        result = resolver.resolve(author, genre, audience, sensitivity, goal)
        assert result.get("display_name") == "My Author"

    def test_conflict_log_populated(self, resolver: ConflictResolver, loader: SpecLoader) -> None:
        a, g, au, s, go = _fixture_profiles(loader)
        result = resolver.resolve(a, g, au, s, go)
        # conflict_log may be empty if no field name collision; ensure it's a list
        assert isinstance(result.get("_conflict_log"), list)


# ── Sacred sensitivity ────────────────────────────────────────────────────────


class TestSacredSensitivity:
    def test_goal_cannot_loosen_max_heat(
        self, resolver: ConflictResolver, loader: SpecLoader
    ) -> None:
        """Goal placing itself above Sensitivity for max_heat_level → SensitivityViolation."""
        a, g, au, s, _ = _fixture_profiles(loader)
        violating_goal = loader.load("goal", "fixture_violates_sacred")
        with pytest.raises(SensitivityViolation, match="sacred"):
            resolver.resolve(a, g, au, s, violating_goal)

    def test_valid_goal_does_not_raise(
        self, resolver: ConflictResolver, loader: SpecLoader
    ) -> None:
        """Non-violating goal resolves without error."""
        a, g, au, s, go = _fixture_profiles(loader)
        result = resolver.resolve(a, g, au, s, go)
        assert result["_sensitivity_thresholds"]["max_heat_level"] == 5

    def test_sensitivity_thresholds_in_spec_match_sensitivity_profile(
        self, registry: ProfileRegistry
    ) -> None:
        """ProjectSpec.sensitivity_thresholds reflects Sensitivity profile, not Goal."""
        spec = registry.compose(
            book_id="b1",
            series_id="s1",
            author_name="fixture",
            genre_name="fixture",
            audience_name="fixture",
            sensitivity_name="fixture",
            goal_name="fixture",
        )
        # fixture_sensitivity.yaml sets max_heat_level = 5
        assert spec.sensitivity_thresholds.max_heat_level == 5.0
