"""BookMetricsLedger — stylometric snapshot per finalized scene.

QualityEvaluator evaluates each scene's contribution to running totals,
not local absolute values. This ledger provides both.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.ledgers.base import BaseLedger


@dataclass
class BookMetricsEvent:
    event_id: str
    book_id: str
    chapter_id: str
    scene_id: str
    timestamp: str
    word_count: int
    interiority_pct: float
    dialogue_ratio: float
    exposition_pct: float
    action_pct: float
    sensory_density_per_1k: float
    em_dash_density: float
    sentence_length_avg: float
    ai_tell_count: int
    no_fly_violations: int
    heat_curve_position: float = 0.0
    sex_scene_flag: bool = False
    character_metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunningTotals:
    word_count_total: int = 0
    sex_scene_count: int = 0
    ai_tell_count_total: int = 0
    no_fly_violations_total: int = 0
    interiority_pct_running: float = 0.0
    dialogue_ratio_running: float = 0.0
    exposition_pct_running: float = 0.0
    sensory_density_running: float = 0.0


class BookMetricsLedger(BaseLedger):
    """Append-only stylometric ledger for a single book."""

    def __init__(self, book_id: str, data_root: Path = Path("data")) -> None:
        db_path = data_root / book_id / "book_metrics.db"
        super().__init__(db_path)
        self._book_id = book_id

    def append(self, event: BookMetricsEvent) -> None:
        payload: dict[str, Any] = {
            "event_id": event.event_id,
            "book_id": event.book_id,
            "chapter_id": event.chapter_id,
            "scene_id": event.scene_id,
            "timestamp": event.timestamp,
            "metrics": {
                "word_count": event.word_count,
                "interiority_pct": event.interiority_pct,
                "dialogue_ratio": event.dialogue_ratio,
                "exposition_pct": event.exposition_pct,
                "action_pct": event.action_pct,
                "sensory_density_per_1k": event.sensory_density_per_1k,
                "em_dash_density": event.em_dash_density,
                "sentence_length_avg": event.sentence_length_avg,
                "ai_tell_count": event.ai_tell_count,
                "no_fly_violations": event.no_fly_violations,
                "heat_curve_position": event.heat_curve_position,
                "sex_scene_flag": event.sex_scene_flag,
            },
            "character_metrics": event.character_metrics,
        }
        self._append(event.event_id, payload)

    def compute_running_totals(self) -> RunningTotals:
        events = self._all_payloads()
        if not events:
            return RunningTotals()

        total_words = 0
        sex_scenes = 0
        ai_tells = 0
        no_fly = 0
        weighted_interiority = 0.0
        weighted_dialogue = 0.0
        weighted_exposition = 0.0
        weighted_sensory = 0.0

        for e in events:
            m = e["metrics"]
            wc = m["word_count"]
            total_words += wc
            if m.get("sex_scene_flag"):
                sex_scenes += 1
            ai_tells += m.get("ai_tell_count", 0)
            no_fly += m.get("no_fly_violations", 0)
            weighted_interiority += m.get("interiority_pct", 0.0) * wc
            weighted_dialogue += m.get("dialogue_ratio", 0.0) * wc
            weighted_exposition += m.get("exposition_pct", 0.0) * wc
            weighted_sensory += m.get("sensory_density_per_1k", 0.0) * wc

        denom = total_words or 1
        return RunningTotals(
            word_count_total=total_words,
            sex_scene_count=sex_scenes,
            ai_tell_count_total=ai_tells,
            no_fly_violations_total=no_fly,
            interiority_pct_running=weighted_interiority / denom,
            dialogue_ratio_running=weighted_dialogue / denom,
            exposition_pct_running=weighted_exposition / denom,
            sensory_density_running=weighted_sensory / denom,
        )

    def budget_remaining(
        self, targets: dict[str, float], word_count_remaining: int
    ) -> dict[str, float]:
        """Headroom between current running total and target, scaled to remaining words."""
        totals = self.compute_running_totals()
        current: dict[str, float] = {
            "interiority_pct": totals.interiority_pct_running,
            "dialogue_ratio": totals.dialogue_ratio_running,
            "exposition_pct": totals.exposition_pct_running,
            "sensory_density_per_1k": totals.sensory_density_running,
        }
        result: dict[str, float] = {}
        for key, target in targets.items():
            actual = current.get(key, 0.0)
            result[key] = (target - actual) * word_count_remaining
        return result
