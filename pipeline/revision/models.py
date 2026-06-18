"""Shared models for book-level revision analysis."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RevisionIssue:
    """One actionable issue for a book or scene revision backlog."""

    category: str
    severity: int
    signal: str
    evidence: str
    recommendation: str
    source: str
    scene_id: str | None = None
    chapter_id: str | None = None
    scope: str = "scene"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def issue_id(self) -> str:
        key = "|".join(
            [
                self.source,
                self.category,
                self.scene_id or "book",
                self.signal,
                self.evidence,
            ]
        )
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        return f"ISS-{_slug(self.category)}-{digest}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "scope": self.scope,
            "scene_id": self.scene_id,
            "chapter_id": self.chapter_id,
            "category": self.category,
            "severity": self.severity,
            "signal": self.signal,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "source": self.source,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AnalyzedScene:
    """Scene-level facts loaded from a completed book run."""

    scene_id: str
    chapter_id: str
    output_path: str
    text: str
    status_word_count: int
    adjusted_word_count_target: int
    revise_count: int
    force_resolved: bool
    eval_voice_consistency: float | None = None
    eval_ai_tell: float | None = None
    metrics: Mapping[str, Any] = field(default_factory=dict)
    quality_scores: Mapping[str, float] = field(default_factory=dict)

    @property
    def target_ratio(self) -> float | None:
        if self.adjusted_word_count_target <= 0:
            return None
        return self.status_word_count / self.adjusted_word_count_target


@dataclass(frozen=True)
class BookRunContext:
    """Book-level facts available to deterministic editorial reviewers."""

    summary_path: str
    summary: Mapping[str, Any]
    scenes: Sequence[AnalyzedScene]
    ledger_dashboard: Mapping[str, Any]
    narrative_counts: Mapping[str, int]
    repeated_phrases: Mapping[str, Sequence[str]]


def sort_issues(issues: Sequence[RevisionIssue]) -> list[RevisionIssue]:
    """Sort issues by severity, then scope, then stable issue ID."""
    return sorted(
        issues,
        key=lambda issue: (
            -issue.severity,
            issue.scope,
            issue.scene_id or "",
            issue.issue_id,
        ),
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "issue"
