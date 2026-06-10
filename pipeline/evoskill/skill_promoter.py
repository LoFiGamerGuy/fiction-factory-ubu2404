"""SkillPromoter — promotes EvoSkill candidates to WUPHF wiki as editorial guidelines."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.evoskill.evoskill_client import CandidateSkill


class SkillPromoter:
    """Converts accepted EvoSkill candidates into editorial-guideline markdown
    and optionally publishes them to the WUPHF wiki.

    When ``wuphf_client`` is ``None`` the promoter operates in local-only mode
    and writes markdown files under ``data/{series_id}/skills/``.
    """

    def __init__(self, wuphf_client: Any | None = None, data_root: Path = Path("data")) -> None:
        self._wuphf = wuphf_client
        self._data_root = data_root

    # ── Public API ────────────────────────────────────────────────────────────

    def promote_to_wiki(self, skill: CandidateSkill, series_id: str) -> None:
        """Promote a skill to the WUPHF wiki and/or local filesystem.

        Converts the skill to markdown, writes a local copy, and — if a
        ``wuphf_client`` was provided — pushes to the remote wiki page at
        ``editorial-guidelines/{series_id}/{skill.skill_id}``.
        """
        markdown = self.skill_to_markdown(skill)

        if self._wuphf is not None:
            wiki_path = f"series-bible/{series_id}/editorial-guidelines/{skill.skill_id}"
            self._wuphf.update_wiki(wiki_path, markdown)

        local_path = self._data_root / series_id / "skills" / f"{skill.skill_id}.md"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(markdown, encoding="utf-8")

    def skill_to_markdown(self, skill: CandidateSkill) -> str:
        """Render a CandidateSkill as an editorial-guideline markdown document."""
        failure_mode_text = skill.failure_mode if skill.failure_mode is not None else "N/A"
        return (
            f"# Skill: {skill.skill_id}\n\n"
            f"## Condition\n\n{skill.condition}\n\n"
            f"## Recommendation\n\n{skill.recommendation}\n\n"
            f"## Failure Mode\n\n{failure_mode_text}\n\n"
            f"## Score\n\n{skill.score}\n\n"
            f"## Proposed At\n\n{skill.proposed_at}\n"
        )
