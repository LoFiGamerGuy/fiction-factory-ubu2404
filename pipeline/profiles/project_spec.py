"""ProjectSpec — frozen resolved profile pentad for one book run.

Produced by ProfileRegistry.compose(). Immutable after creation.
Pinned versions guarantee reproducibility: same versions + same inputs = same spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResolvedVoiceAxes:
    sentence_length_mean: float = 14.0
    sentence_length_std: float = 4.0
    lexical_diversity_target: float = 70.0
    dialogue_to_narration_ratio: float = 0.40
    internal_monologue_share: float = 0.20
    em_dash_rate_max: float = 5.0
    modal_hedge_frequency: float = 3.0
    pov_distance_default: str = "close_third"


@dataclass(frozen=True)
class ResolvedGenreConfig:
    genre_name: str = ""
    genre_module_status: str = "scaffold"
    scene_function_vocabulary: tuple[str, ...] = ()
    word_count_min: int = 60000
    word_count_max: int = 100000
    chapter_count_min: int = 20
    chapter_count_max: int = 40
    reader_contract: tuple[str, ...] = ()
    heat_scale_min: int = 1
    heat_scale_max: int = 5


@dataclass(frozen=True)
class ResolvedSensitivityThresholds:
    max_heat_level: float = 5.0
    max_violence_intensity: float = 5.0
    content_domain_policies: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedGoalWeights:
    intent: str = "series_brand"
    critic_weights: dict[str, float] = field(default_factory=dict)
    reader_weights: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedAudienceExpectations:
    reader_lens: str = ""
    expectation_set: tuple[str, ...] = ()
    dnf_triggers: tuple[str, ...] = ()
    satisfaction_triggers: tuple[str, ...] = ()


@dataclass
class ProjectSpec:
    """Resolved profile pentad for one book run.

    ``is_frozen`` is set True by ProfileRegistry after composition. Once frozen,
    no field should be mutated; the dataclass is not technically frozen to allow
    creation helpers, but callers must treat it as immutable.
    """

    book_id: str
    series_id: str
    voice_axes: ResolvedVoiceAxes
    genre_config: ResolvedGenreConfig
    sensitivity_thresholds: ResolvedSensitivityThresholds
    goal_weights: ResolvedGoalWeights
    audience_expectations: ResolvedAudienceExpectations
    profile_versions: dict[str, str] = field(default_factory=dict)
    composition_timestamp: str = ""
    is_frozen: bool = False
    raw_profiles: dict[str, Any] = field(default_factory=dict)
