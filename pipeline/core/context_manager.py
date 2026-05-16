"""ContextManager — three-tier context assembly with LedgerManager integration.

Scene tier  : current scene brief + recent scene history (last N scenes).
Book tier   : series bible excerpt + chapter summaries.
Series tier : series-level facts + cross-book promise state (non-negotiable).

Size enforcement: if total context exceeds budget, truncate scene tier first,
then book tier. Series tier is never truncated.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pipeline.core.job_context import JobContext
    from pipeline.core.project_layout import ProjectLayout
    from pipeline.ledgers.ledger_manager import LedgerManager

logger = logging.getLogger(__name__)

# Character budgets per tier (approximate; 1 token ≈ 4 chars)
SCENE_TIER_MAX_CHARS: int = 8_000
BOOK_TIER_MAX_CHARS: int = 4_000
SERIES_TIER_MAX_CHARS: int = 2_000
# Recent scene entries to include in scene tier
SCENE_TIER_HISTORY_COUNT: int = 3


@dataclass
class ContextBundle:
    """Assembled context for one scene generation pass."""

    scene_tier: str
    book_tier: str
    series_tier: str
    author_dashboard_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def total_chars(self) -> int:
        return len(self.scene_tier) + len(self.book_tier) + len(self.series_tier)

    def as_tiers_dict(self) -> dict[str, str]:
        return {
            "scene": self.scene_tier,
            "book": self.book_tier,
            "series": self.series_tier,
        }


class ContextManager:
    """Assembles minimum-necessary context for each scene generation pass.

    Injects AuthorDashboard from LedgerManager into every bundle so agents
    always have the latest ledger state available in context.
    """

    def __init__(
        self,
        project_layout: ProjectLayout,
        ledger_manager: LedgerManager,
        *,
        scene_tier_max_chars: int = SCENE_TIER_MAX_CHARS,
        book_tier_max_chars: int = BOOK_TIER_MAX_CHARS,
        series_tier_max_chars: int = SERIES_TIER_MAX_CHARS,
    ) -> None:
        self._layout = project_layout
        self._ledger = ledger_manager
        self._scene_max = scene_tier_max_chars
        self._book_max = book_tier_max_chars
        self._series_max = series_tier_max_chars

    # ── Public API ────────────────────────────────────────────────────────────

    def assemble(
        self,
        job_context: JobContext,
        scene_brief: str = "",
    ) -> ContextBundle:
        """Assemble a ContextBundle for the given scene.

        ``scene_brief`` populates the scene tier; book and series tiers are
        populated from files if they exist (gracefully empty otherwise).
        AuthorDashboard from LedgerManager is always injected.
        """
        scene_tier = self._build_scene_tier(job_context.book_id, job_context.scene_id, scene_brief)
        book_tier = self._build_book_tier()
        series_tier = self._build_series_tier()

        scene_tier, book_tier, series_tier = self._enforce_size_limits(
            scene_tier, book_tier, series_tier
        )

        dashboard_summary = self._get_dashboard_summary(job_context.book_id, job_context.scene_id)

        return ContextBundle(
            scene_tier=scene_tier,
            book_tier=book_tier,
            series_tier=series_tier,
            author_dashboard_summary=dashboard_summary,
        )

    # ── Tier builders ─────────────────────────────────────────────────────────

    def _build_scene_tier(self, book_id: str, scene_id: str, scene_brief: str) -> str:
        parts: list[str] = []
        if scene_brief:
            parts.append(f"## Current Scene Brief\n{scene_brief}")

        history = self._load_scene_history(SCENE_TIER_HISTORY_COUNT)
        if history:
            parts.append(f"## Recent Scene History\n{history}")

        return "\n\n".join(parts)

    def _build_book_tier(self) -> str:
        bible_path = self._layout.series_bible_path()
        if not bible_path.exists():
            return ""
        content = bible_path.read_text(encoding="utf-8")
        return content[: self._book_max]

    def _build_series_tier(self) -> str:
        facts_path = self._layout.series_facts_path()
        if not facts_path.exists():
            return ""
        content = facts_path.read_text(encoding="utf-8")
        return content[: self._series_max]

    def _load_scene_history(self, count: int) -> str:
        history_path = self._layout.scene_history_path()
        if not history_path.exists():
            return ""
        try:
            lines = history_path.read_text(encoding="utf-8").strip().splitlines()
            recent = lines[-count:] if len(lines) > count else lines
            entries: list[str] = []
            for line in recent:
                try:
                    entry = json.loads(line)
                    entries.append(entry.get("summary", ""))
                except json.JSONDecodeError:
                    continue
            return "\n\n".join(e for e in entries if e)
        except OSError as exc:
            logger.warning("Scene history read failed: %s", exc)
            return ""

    def _get_dashboard_summary(self, book_id: str, scene_id: str) -> dict[str, Any]:
        try:
            dashboard = self._ledger.get_dashboard_summary(book_id, scene_id)
            return dataclasses.asdict(dashboard)
        except Exception as exc:
            logger.warning("AuthorDashboard fetch failed (non-fatal): %s", exc)
            return {}

    # ── Size enforcement ──────────────────────────────────────────────────────

    def _enforce_size_limits(self, scene: str, book: str, series: str) -> tuple[str, str, str]:
        """Truncate tiers to fit within budgets.

        Scene is truncated first; book second; series is non-negotiable.
        Per-tier caps are applied independently so agents never receive
        unexpectedly large context from a single tier.
        """
        # Per-tier caps
        if len(scene) > self._scene_max:
            scene = scene[: self._scene_max]
        if len(book) > self._book_max:
            book = book[: self._book_max]
        if len(series) > self._series_max:
            series = series[: self._series_max]

        return scene, book, series
