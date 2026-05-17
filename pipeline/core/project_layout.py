"""ProjectLayout — canonical path assembly for all pipeline artefacts.

No agent or module constructs paths by string concatenation. Every path goes
through ProjectLayout. This prevents the path-fragmentation anti-pattern (MBSE B1).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProjectLayout:
    """All path assembly for one series/book run.

    ``series_root`` is the root of the series directory tree.
    ``book_id`` identifies the current book within the series.
    """

    series_root: Path
    book_id: str

    # ── Series-level paths ────────────────────────────────────────────────────

    def series_spec_path(self) -> Path:
        return self.series_root / "spec.yaml"

    def series_bible_path(self) -> Path:
        return self.series_root / "data" / "series" / "bible.md"

    def series_facts_path(self) -> Path:
        return self.series_root / "data" / "series" / "series_facts.md"

    def cost_log_path(self) -> Path:
        return self.series_root / "data" / "cost_log.jsonl"

    # ── Book-level paths ──────────────────────────────────────────────────────

    def book_dir(self) -> Path:
        return self.series_root / "data" / "books" / self.book_id

    def book_spec_path(self) -> Path:
        return self.book_dir() / "spec.yaml"

    def scene_history_path(self) -> Path:
        return self.book_dir() / "scene_history.jsonl"

    def manuscript_path(self) -> Path:
        return self.book_dir() / "manuscript.md"

    # ── Scene-level paths ─────────────────────────────────────────────────────

    def scene_inventory_path(self) -> Path:
        return self.book_dir() / "scene_inventory.json"

    def scene_output_path(self, chapter: int, scene: int) -> Path:
        return self.book_dir() / "scenes" / f"ch{chapter:02d}_sc{scene:02d}.md"

    def scene_draft_path(self, chapter: int, scene: int) -> Path:
        return self.book_dir() / "drafts" / f"ch{chapter:02d}_sc{scene:02d}_draft.md"

    # ── Ledger paths ──────────────────────────────────────────────────────────

    def ledger_db_path(self, ledger_name: str) -> Path:
        return self.book_dir() / "ledgers" / f"{ledger_name}.db"

    # ── Context pack paths ────────────────────────────────────────────────────

    def context_pack_path(self, agent_id: str, scene_id: str) -> Path:
        return self.book_dir() / "context_packs" / agent_id / f"{scene_id}.json"

    def provenance_path(self, agent_id: str, scene_id: str) -> Path:
        return self.book_dir() / "context_packs" / agent_id / f"{scene_id}_provenance.json"

    # ── Log paths ─────────────────────────────────────────────────────────────

    def agent_log_path(self, agent_id: str) -> Path:
        return self.book_dir() / "logs" / f"{agent_id}.jsonl"
