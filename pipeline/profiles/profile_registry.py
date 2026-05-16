"""ProfileRegistry — loads and composes the 5-profile pentad into a ProjectSpec.

Validates all 5 profiles before composing. Returns an immutable ProjectSpec
with pinned versions for reproducibility.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline.profiles.conflict_resolver import ConflictResolver
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)
from pipeline.profiles.spec_loader import SpecLoader


class ProfileRegistry:
    """Orchestrates loading all 5 profiles and resolving them into a ProjectSpec."""

    def __init__(self, workspace_root: Path = Path(".")) -> None:
        self._loader = SpecLoader(workspace_root)
        self._resolver = ConflictResolver()

    def compose(
        self,
        book_id: str,
        series_id: str,
        author_name: str,
        genre_name: str,
        audience_name: str,
        sensitivity_name: str,
        goal_name: str,
    ) -> ProjectSpec:
        """Load all 5 profiles, validate, resolve conflicts, return frozen ProjectSpec."""
        author = self._loader.load("author", author_name)
        genre = self._loader.load("genre", genre_name)
        audience = self._loader.load("audience", audience_name)
        sensitivity = self._loader.load("sensitivity", sensitivity_name)
        goal = self._loader.load("goal", goal_name)

        resolved = self._resolver.resolve(author, genre, audience, sensitivity, goal)

        spec = ProjectSpec(
            book_id=book_id,
            series_id=series_id,
            voice_axes=_build_voice_axes(resolved.get("_resolved_voice_axes", {})),
            genre_config=_build_genre_config(resolved.get("_resolved_genre", {})),
            sensitivity_thresholds=_build_sensitivity(resolved.get("_sensitivity_thresholds", {})),
            goal_weights=_build_goal_weights(resolved.get("_goal_weights", {})),
            audience_expectations=_build_audience(resolved.get("_audience_expectations", {})),
            profile_versions=resolved.get("_profile_versions", {}),
            composition_timestamp=datetime.now(UTC).isoformat(),
            is_frozen=True,
            raw_profiles={
                "author": author,
                "genre": genre,
                "audience": audience,
                "sensitivity": sensitivity,
                "goal": goal,
            },
        )
        return spec


def _build_voice_axes(axes: dict[str, Any]) -> ResolvedVoiceAxes:
    sentence = axes.get("sentence_level", {})
    lexical = axes.get("lexical", {})
    dialogue = axes.get("dialogue", {})
    subtext = axes.get("subtext", {})
    cadence = axes.get("cadence", {})
    return ResolvedVoiceAxes(
        sentence_length_mean=sentence.get("length_mean_words", 14.0),
        sentence_length_std=sentence.get("length_std_words", 4.0),
        lexical_diversity_target=lexical.get("diversity_target", 70.0),
        dialogue_to_narration_ratio=dialogue.get("to_narration_ratio", 0.40),
        internal_monologue_share=dialogue.get("internal_monologue_share", 0.20),
        em_dash_rate_max=cadence.get("em_dash_per_1k_max", 5.0),
        modal_hedge_frequency=subtext.get("modal_hedge_per_1k", 3.0),
        pov_distance_default="close_third",
    )


def _build_genre_config(genre: dict[str, Any]) -> ResolvedGenreConfig:
    sc = genre.get("structural_conventions", {})
    wc = sc.get("word_count_range", {})
    cc = sc.get("chapter_count_range", {})
    hs = genre.get("heat_scale", {})
    return ResolvedGenreConfig(
        genre_name=genre.get("genre_name", ""),
        genre_module_status=genre.get("genre_module_status", "scaffold"),
        scene_function_vocabulary=tuple(genre.get("scene_function_vocabulary", [])),
        word_count_min=wc.get("min", 60000),
        word_count_max=wc.get("max", 100000),
        chapter_count_min=cc.get("min", 20),
        chapter_count_max=cc.get("max", 40),
        reader_contract=tuple(genre.get("reader_contract", [])),
        heat_scale_min=hs.get("min", 1),
        heat_scale_max=hs.get("max", 5),
    )


def _build_sensitivity(thresholds: dict[str, Any]) -> ResolvedSensitivityThresholds:
    return ResolvedSensitivityThresholds(
        max_heat_level=float(thresholds.get("max_heat_level", 5.0)),
        max_violence_intensity=float(thresholds.get("max_violence_intensity", 5.0)),
        content_domain_policies=thresholds,
    )


def _build_goal_weights(goal: dict[str, Any]) -> ResolvedGoalWeights:
    return ResolvedGoalWeights(
        intent=goal.get("intent", "series_brand"),
        critic_weights=goal.get("critic_weights", {}),
        reader_weights=goal.get("reader_weights", {}),
    )


def _build_audience(aud: dict[str, Any]) -> ResolvedAudienceExpectations:
    return ResolvedAudienceExpectations(
        reader_lens=aud.get("reader_lens", ""),
        expectation_set=tuple(aud.get("expectation_set", [])),
        dnf_triggers=tuple(aud.get("dnf_triggers", [])),
        satisfaction_triggers=tuple(aud.get("satisfaction_triggers", [])),
    )
