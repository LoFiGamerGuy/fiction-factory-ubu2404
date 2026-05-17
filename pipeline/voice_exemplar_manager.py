"""VoiceExemplarManager — manages exemplar pool for voice consistency.

Dr. Smith spec invariants (non-negotiable):
  - Exactly 2 exemplars per call (n=2 is the only supported value).
  - Exemplar window: 200–400 words (hard bounds; ValueError if violated).
  - 3-tier source hierarchy: user_provided → calibration_corpus → synthetic_fallback.
  - Uniform random rotation with beat-type stratification.
  - Collapse detector: warns when same exemplar appears > 50% of last K calls.
  - add_generated_content() always raises ValueError — no auto-add.
"""

from __future__ import annotations

import logging
import random
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

logger = logging.getLogger(__name__)

_MIN_WORDS = 200
_MAX_WORDS = 400
_COLLAPSE_WINDOW = 10  # number of recent calls to check
_COLLAPSE_THRESHOLD = 0.5  # >50% same exemplar → CollapseWarning

_VALID_TIERS = frozenset({"user_provided", "calibration_corpus", "synthetic_fallback"})
_TIER_PRIORITY = {"user_provided": 0, "calibration_corpus": 1, "synthetic_fallback": 2}


class CollapseWarning(UserWarning):
    """Raised when the exemplar rotation is collapsing to the same exemplar."""


@dataclass
class Exemplar:
    text: str
    source_tier: str
    exemplar_id: str
    beat_type: str | None = None

    def __post_init__(self) -> None:
        word_count = len(self.text.split())
        if not (_MIN_WORDS <= word_count <= _MAX_WORDS):
            raise ValueError(
                f"Exemplar '{self.exemplar_id}' has {word_count} words; "
                f"must be {_MIN_WORDS}–{_MAX_WORDS} words."
            )
        if self.source_tier not in _VALID_TIERS:
            raise ValueError(
                f"source_tier must be one of {sorted(_VALID_TIERS)}, got {self.source_tier!r}"
            )


class CollapseDetector:
    """Tracks recent exemplar selections; warns on rotation collapse."""

    def __init__(self, window: int = _COLLAPSE_WINDOW) -> None:
        self._window = window
        self._history: list[str] = []  # exemplar_ids, most-recent last

    def record(self, exemplar_ids: list[str]) -> None:
        self._history.extend(exemplar_ids)
        if len(self._history) > self._window * 2:
            self._history = self._history[-self._window * 2 :]

    def check(self) -> None:
        recent = self._history[-self._collapse_count :]
        if len(recent) < self._collapse_count:
            return
        from collections import Counter

        counts = Counter(recent)
        most_common_id, most_common_n = counts.most_common(1)[0]
        ratio = most_common_n / len(recent)
        if ratio > _COLLAPSE_THRESHOLD:
            warnings.warn(
                f"CollapseDetector: exemplar '{most_common_id}' appeared in "
                f"{most_common_n}/{len(recent)} recent calls ({ratio:.0%}). "
                "Rotation is collapsing — consider expanding the exemplar pool.",
                CollapseWarning,
                stacklevel=3,
            )

    @property
    def _collapse_count(self) -> int:
        return self._window


class VoiceExemplarManager:
    """Manages exemplar pool for WriterAgent voice consistency."""

    _EXACTLY_N: ClassVar[int] = 2  # always exactly 2 exemplars per call

    def __init__(
        self,
        exemplar_pool: list[Exemplar],
        rng: random.Random | None = None,
    ) -> None:
        if len(exemplar_pool) < 3:
            raise ValueError(
                f"Exemplar pool must have ≥ 3 exemplars for collapse detection; "
                f"got {len(exemplar_pool)}."
            )
        self._pool = list(exemplar_pool)
        self._rng = rng or random.Random()
        self._collapse = CollapseDetector()

    def get_exemplars(
        self,
        beat_type: str | None = None,
        n: int = _EXACTLY_N,
    ) -> list[Exemplar]:
        """Return exactly n exemplars.

        3-tier priority: user_provided → calibration_corpus → synthetic_fallback.
        Within each tier, prefer exemplars matching beat_type (if given), then
        uniform random rotation.
        """
        if n != self._EXACTLY_N:
            raise ValueError(f"n must be {self._EXACTLY_N}; got {n}")

        selected: list[Exemplar] = []
        remaining = [e for e in self._pool if e not in selected]

        for tier in ("user_provided", "calibration_corpus", "synthetic_fallback"):
            if len(selected) >= n:
                break
            tier_pool = [e for e in remaining if e.source_tier == tier]
            if not tier_pool:
                continue

            # Prefer matching beat_type within tier
            if beat_type:
                matched = [e for e in tier_pool if e.beat_type == beat_type]
                not_matched = [e for e in tier_pool if e.beat_type != beat_type]
                ordered = matched + not_matched
            else:
                ordered = tier_pool

            need = n - len(selected)
            chosen = self._rng.sample(ordered, min(need, len(ordered)))
            selected.extend(chosen)
            remaining = [e for e in remaining if e not in selected]

        if len(selected) < n:
            # Fallback: fill from any remaining
            need = n - len(selected)
            available = [e for e in self._pool if e not in selected]
            extra = self._rng.sample(available, min(need, len(available)))
            selected.extend(extra)

        result = selected[:n]
        self._collapse.record([e.exemplar_id for e in result])
        self._collapse.check()
        return result

    def record_usage(
        self,
        scene_id: str,
        exemplars_used: list[Exemplar],
        provenance_path: Path | None = None,
    ) -> None:
        """Log provenance of exemplar usage for a scene."""
        import json
        from datetime import UTC, datetime

        entry = {
            "scene_id": scene_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "exemplars": [
                {
                    "exemplar_id": e.exemplar_id,
                    "source_tier": e.source_tier,
                    "beat_type": e.beat_type,
                }
                for e in exemplars_used
            ],
        }
        logger.debug("VoiceExemplarManager: recorded usage for %s", scene_id)
        if provenance_path:
            provenance_path.parent.mkdir(parents=True, exist_ok=True)
            with provenance_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")

    def add_generated_content(self, text: str) -> None:  # noqa: ARG002
        """Hard invariant: never add generated content to the exemplar pool."""
        raise ValueError(
            "Cannot auto-add generated content to exemplar pool. "
            "Exemplars must be user-provided or from calibration corpus."
        )
