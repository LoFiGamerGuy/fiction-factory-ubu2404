"""ConflictResolver — resolves profile field conflicts using 7-level precedence.

Precedence (highest first): Constraint > Sensitivity > Goal > Genre > Audience > Author > Universal

Sacred rule: Sensitivity hard_thresholds cannot be loosened by any other profile.
Any attempt raises SensitivityViolation — never silently overridden.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Ordered precedence: index 0 = highest authority
_PRECEDENCE = ["sensitivity", "goal", "genre", "audience", "author", "universal"]

# Sensitivity threshold fields that are sacred (Goal cannot loosen these)
_SACRED_THRESHOLD_KEYS = {"max_heat_level", "max_violence_intensity"}


class SensitivityViolation(Exception):  # noqa: N818
    """Raised when a profile attempts to loosen a sacred Sensitivity threshold."""


class ConflictResolver:
    """Resolves per-field conflicts across the 5 profile types using precedence rules."""

    def resolve(
        self,
        author: dict[str, Any],
        genre: dict[str, Any],
        audience: dict[str, Any],
        sensitivity: dict[str, Any],
        goal: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge all profiles into a single resolved dict.

        Returns a flat dict with all resolved fields plus:
        - ``_resolved_voices``: resolved voice axis values
        - ``_resolved_genre``: resolved genre config
        - ``_sensitivity_thresholds``: sacred hard thresholds
        - ``_goal_weights``: resolved critic/reader weights
        - ``_audience_expectations``: resolved audience config
        - ``_profile_versions``: version strings keyed by profile type
        - ``_conflict_log``: list of resolved conflicts (for DECISIONS.md)
        """
        conflict_log: list[dict[str, Any]] = []

        profiles_by_precedence: list[tuple[str, dict[str, Any]]] = [
            ("sensitivity", sensitivity),
            ("goal", goal),
            ("genre", genre),
            ("audience", audience),
            ("author", author),
        ]

        resolved: dict[str, Any] = {}
        for _level, profile in reversed(profiles_by_precedence):
            for key, value in profile.items():
                if key.startswith("_"):
                    continue
                if key in resolved and resolved[key] != value:
                    conflict_log.append(
                        {
                            "field": key,
                            "winner": _level,
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
                resolved[key] = value

        self._check_sacred_thresholds(sensitivity, goal)

        # Build typed sub-objects
        resolved["_sensitivity_thresholds"] = sensitivity.get("hard_thresholds", {})
        resolved["_goal_weights"] = {
            "intent": goal.get("intent", "series_brand"),
            "critic_weights": goal.get("weight_overrides", {}).get("critic_weights", {}),
            "reader_weights": goal.get("weight_overrides", {}).get("reader_weights", {}),
        }
        resolved["_resolved_genre"] = {
            "genre_name": genre.get("genre_name", ""),
            "genre_module_status": genre.get("genre_module_status", "scaffold"),
            "scene_function_vocabulary": genre.get("scene_function_vocabulary", []),
            "structural_conventions": genre.get("structural_conventions", {}),
            "reader_contract": genre.get("reader_contract", []),
            "heat_scale": genre.get("heat_scale", {"min": 1, "max": 5}),
        }
        resolved["_resolved_voice_axes"] = author.get("voice_axes", {})
        resolved["_audience_expectations"] = {
            "reader_lens": audience.get("reader_lens", ""),
            "expectation_set": audience.get("expectation_set", []),
            "dnf_triggers": audience.get("trigger_sets", {}).get("dnf_triggers", []),
            "satisfaction_triggers": audience.get("trigger_sets", {}).get(
                "satisfaction_triggers", []
            ),
        }
        resolved["_profile_versions"] = {
            "author": author.get("version", ""),
            "genre": genre.get("version", ""),
            "audience": audience.get("version", ""),
            "sensitivity": sensitivity.get("version", ""),
            "goal": goal.get("version", ""),
        }
        resolved["_conflict_log"] = conflict_log

        if conflict_log:
            logger.info(
                "ConflictResolver: %d field conflicts resolved",
                len(conflict_log),
            )

        return resolved

    @staticmethod
    def _check_sacred_thresholds(
        sensitivity: dict[str, Any],
        goal: dict[str, Any],
    ) -> None:
        """Raise SensitivityViolation if goal attempts to loosen any sacred threshold."""
        sacred = sensitivity.get("hard_thresholds", {})
        # Goal weight overrides don't directly set thresholds, but check if goal
        # explicitly tries to loosen via conflict_precedence_rules for sacred fields.
        for rule in goal.get("conflict_precedence_rules", []):
            axis = rule.get("axis", "")
            if axis not in _SACRED_THRESHOLD_KEYS:
                continue
            order = rule.get("precedence_order", [])
            if not order:
                continue
            # If goal places itself above sensitivity for a sacred axis → violation
            if "goal" in order and "sensitivity" in order:
                goal_idx = order.index("goal")
                sensitivity_idx = order.index("sensitivity")
                if goal_idx < sensitivity_idx:
                    threshold_value = sacred.get(axis)
                    raise SensitivityViolation(
                        f"Goal profile attempts to loosen sacred Sensitivity threshold "
                        f"'{axis}' (value={threshold_value}). "
                        "Sensitivity thresholds are sacred and cannot be overridden."
                    )
