"""BookStructurePlanner — reads series/book spec, generates full scene inventory.

Heat level per scene is interpolated from the genre profile heat_curve.
Scene inventory is written to {book_dir}/scene_inventory.json.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Waypoints for standard heat curves: [(position, max_heat), ...]
_DEFAULT_HEAT_CURVES: dict[str, list[tuple[float, int]]] = {
    "rising": [(0.0, 1), (0.3, 2), (0.6, 3), (1.0, 5)],
    "flat": [(0.0, 3), (1.0, 3)],
    "escalating": [(0.0, 2), (0.5, 3), (1.0, 5)],
    "moderate": [(0.0, 2), (0.5, 3), (1.0, 4)],
}


@dataclass
class SceneSlot:
    scene_id: str
    chapter: int
    act: int
    scene_number: int
    word_count_target: int
    scene_function: str
    heat_level_target: int
    position: float  # 0.0–1.0 in book
    required_slot_id: str | None = None


@dataclass
class SceneInventory:
    book_id: str
    series_id: str
    total_scenes: int
    word_count_target: int
    scenes: list[SceneSlot] = field(default_factory=list)

    @classmethod
    def from_path(cls, inventory_path: Path) -> SceneInventory:
        """Load a persisted scene inventory from JSON."""
        raw: dict[str, Any] = json.loads(inventory_path.read_text(encoding="utf-8"))
        slots = [SceneSlot(**scene) for scene in raw["scenes"]]
        return cls(
            book_id=str(raw["book_id"]),
            series_id=str(raw["series_id"]),
            total_scenes=int(raw["total_scenes"]),
            word_count_target=int(raw["word_count_target"]),
            scenes=slots,
        )


def _interpolate_heat(position: float, waypoints: list[tuple[float, int]]) -> int:
    """Linear interpolation between waypoints; clamps to [waypoints[0], waypoints[-1]]."""
    if not waypoints:
        return 1
    if position <= waypoints[0][0]:
        return waypoints[0][1]
    if position >= waypoints[-1][0]:
        return waypoints[-1][1]
    for i in range(len(waypoints) - 1):
        p0, h0 = waypoints[i]
        p1, h1 = waypoints[i + 1]
        if p0 <= position <= p1:
            if p1 == p0:
                return h0
            t = (position - p0) / (p1 - p0)
            return round(h0 + t * (h1 - h0))
    return waypoints[-1][1]


class BookStructurePlanner:
    """Generates a full scene inventory from series + book spec data."""

    def plan(
        self,
        book_id: str,
        series_id: str,
        series_spec: dict[str, Any],
        book_spec: dict[str, Any],
        book_dir: Path,
        inventory_path: Path | None = None,
    ) -> SceneInventory:
        """Generate scene inventory and write it to book_dir/scene_inventory.json."""
        genre_config = series_spec.get("genre_config", {})
        chapter_count = int(book_spec.get("chapter_count", genre_config.get("chapter_count", 30)))
        scenes_per_chapter = int(book_spec.get("scenes_per_chapter", 2))
        total_scenes = chapter_count * scenes_per_chapter
        word_count_target = int(
            book_spec.get("word_count_target", genre_config.get("word_count_target", 80000))
        )
        words_per_scene = max(600, word_count_target // total_scenes)

        heat_curve_name = genre_config.get("heat_curve", "rising")
        heat_waypoints = _DEFAULT_HEAT_CURVES.get(heat_curve_name, _DEFAULT_HEAT_CURVES["rising"])
        # Also allow waypoints specified in spec directly
        raw_waypoints = genre_config.get("heat_curve_waypoints")
        if raw_waypoints and isinstance(raw_waypoints, list):
            heat_waypoints = [(float(p), int(h)) for p, h in raw_waypoints]

        # Scene function vocabulary — check genre_config first, then series_spec top level
        _default_funcs = ["meet_cute", "escalation", "black_moment", "climax", "resolution"]
        scene_functions = list(
            genre_config.get("scene_function_vocabulary")
            or series_spec.get("scene_function_vocabulary")
            or _default_funcs
        )
        required_slots: list[str] = list(
            genre_config.get("required_scene_slots")
            or series_spec.get("required_scene_slots")
            or []
        )

        # Act proportions: act1≈25%, act2≈50%, act3≈25%
        act1_end = int(total_scenes * 0.25)
        act2_end = int(total_scenes * 0.75)

        scenes: list[SceneSlot] = []
        required_slot_idx = 0

        for idx in range(total_scenes):
            chapter = idx // scenes_per_chapter + 1
            scene_number = idx % scenes_per_chapter + 1
            position = idx / max(1, total_scenes - 1)

            if idx < act1_end:
                act = 1
            elif idx < act2_end:
                act = 2
            else:
                act = 3

            heat = _interpolate_heat(position, heat_waypoints)
            func = scene_functions[idx % len(scene_functions)] if scene_functions else "scene"

            req_slot: str | None = None
            if required_slots and required_slot_idx < len(required_slots):
                # Distribute required slots evenly across the book
                slot_id = required_slots[required_slot_idx]
                if slot_id in {"HEA", "HFN", "HEA_or_HFN"}:
                    expected_idx = total_scenes - 1
                else:
                    expected_idx = int(required_slot_idx * total_scenes / len(required_slots))
                if idx >= expected_idx:
                    req_slot = slot_id
                    required_slot_idx += 1

            scene_id = f"ch{chapter:02d}_sc{scene_number:02d}"
            scenes.append(
                SceneSlot(
                    scene_id=scene_id,
                    chapter=chapter,
                    act=act,
                    scene_number=scene_number,
                    word_count_target=words_per_scene,
                    scene_function=func,
                    heat_level_target=heat,
                    position=round(position, 4),
                    required_slot_id=req_slot,
                )
            )

        inventory = SceneInventory(
            book_id=book_id,
            series_id=series_id,
            total_scenes=total_scenes,
            word_count_target=word_count_target,
            scenes=scenes,
        )

        target_path = inventory_path or book_dir / "scene_inventory.json"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            json.dumps(
                {
                    "book_id": inventory.book_id,
                    "series_id": inventory.series_id,
                    "total_scenes": inventory.total_scenes,
                    "word_count_target": inventory.word_count_target,
                    "scenes": [asdict(s) for s in inventory.scenes],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info("BookStructurePlanner: wrote %d scenes to %s", total_scenes, target_path)
        return inventory
