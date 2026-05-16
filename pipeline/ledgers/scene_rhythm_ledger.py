"""SceneRhythmLedger — in-memory rolling window of recent scene types.

No SQLite: a rolling window of the last N scene types is sufficient and
simpler. LedgerManager holds the single instance per run.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class SceneRhythmEntry:
    scene_id: str
    scene_type: str  # action/dialogue/introspection/transition/sex/aftermath/setup


class SceneRhythmLedger:
    """Rolling window of the last ``window`` scene types (default 10)."""

    def __init__(self, window: int = 10) -> None:
        self._window = window
        self._history: deque[SceneRhythmEntry] = deque(maxlen=window)

    def append(self, entry: SceneRhythmEntry) -> None:
        self._history.append(entry)

    def recent_types(self) -> list[str]:
        return [e.scene_type for e in self._history]

    def last_type(self) -> str | None:
        if not self._history:
            return None
        return self._history[-1].scene_type

    def consecutive_count(self, scene_type: str) -> int:
        """Count how many trailing scenes share the given type."""
        count = 0
        for entry in reversed(self._history):
            if entry.scene_type == scene_type:
                count += 1
            else:
                break
        return count
