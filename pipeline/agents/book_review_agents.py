"""Deterministic book-level editorial reviewers.

These are no-live reviewers: they inspect completed run artifacts and emit
revision backlog issues. They do not rewrite prose or call an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.revision.models import AnalyzedScene, BookRunContext, RevisionIssue


@dataclass(frozen=True)
class BaseBookReviewer:
    """Base class for deterministic book-level reviewer agents."""

    reviewer_id: str

    def review(self, context: BookRunContext) -> list[RevisionIssue]:
        raise NotImplementedError


class BookPacingReviewer(BaseBookReviewer):
    def __init__(self) -> None:
        super().__init__(reviewer_id="book_pacing_reviewer")

    def review(self, context: BookRunContext) -> list[RevisionIssue]:
        issues: list[RevisionIssue] = []
        rhythm = [str(item) for item in context.ledger_dashboard.get("scene_rhythm", [])]
        if len(rhythm) >= 5 and len(set(rhythm[-5:])) == 1:
            issues.append(
                RevisionIssue(
                    scope="book",
                    scene_id=None,
                    category="scene_rhythm",
                    severity=4,
                    signal="repeated_trailing_scene_type",
                    evidence=f"Last {len(rhythm[-5:])} tracked scenes are all '{rhythm[-1]}'.",
                    recommendation=(
                        "Vary scene function labels and force at least one dialogue, "
                        "aftermath, or introspection beat in the next planning pass."
                    ),
                    source=self.reviewer_id,
                    metadata={"scene_rhythm": rhythm},
                )
            )

        for scene in context.scenes:
            ratio = scene.target_ratio
            if ratio is not None and ratio < 0.95:
                issues.append(
                    _scene_issue(
                        scene,
                        category="word_budget",
                        severity=3,
                        signal="scene_under_target",
                        evidence=(
                            f"{scene.status_word_count} words vs adjusted target "
                            f"{scene.adjusted_word_count_target} ({ratio:.2f}x)."
                        ),
                        recommendation=(
                            "Expand the scene with concrete beats before any line-level polishing."
                        ),
                        source=self.reviewer_id,
                    )
                )
            if ratio is not None and ratio > 1.25:
                issues.append(
                    _scene_issue(
                        scene,
                        category="word_budget",
                        severity=3,
                        signal="scene_over_target",
                        evidence=(
                            f"{scene.status_word_count} words vs adjusted target "
                            f"{scene.adjusted_word_count_target} ({ratio:.2f}x)."
                        ),
                        recommendation=(
                            "Compress exposition or merge repeated emotional beats before "
                            "revising adjacent scenes."
                        ),
                        source=self.reviewer_id,
                    )
                )
            if scene.revise_count >= 2:
                issues.append(
                    _scene_issue(
                        scene,
                        category="convergence",
                        severity=4,
                        signal="multiple_revisions_needed",
                        evidence=(
                            f"Scene required {scene.revise_count} revision attempts before GO."
                        ),
                        recommendation=(
                            "Review the scene brief and generated prose together; the quality "
                            "loop had to work hard to land it."
                        ),
                        source=self.reviewer_id,
                    )
                )

        return issues


class RomanceArcReviewer(BaseBookReviewer):
    def __init__(self) -> None:
        super().__init__(reviewer_id="romance_arc_reviewer")

    def review(self, context: BookRunContext) -> list[RevisionIssue]:
        issues: list[RevisionIssue] = []
        intimacy_count = context.narrative_counts.get("intimacy", 0)
        if intimacy_count == 0:
            issues.append(
                RevisionIssue(
                    scope="book",
                    scene_id=None,
                    category="romance_arc",
                    severity=5,
                    signal="no_intimacy_ledger_events",
                    evidence=(
                        "The IntimacyEscalationLedger has no runtime events for this "
                        "completed romance run."
                    ),
                    recommendation=(
                        "Extract or author intimacy escalation beats so the revision pass "
                        "can verify relationship progression rather than relying on prose vibes."
                    ),
                    source=self.reviewer_id,
                )
            )
        if not context.ledger_dashboard.get("intimacy_pairs"):
            issues.append(
                RevisionIssue(
                    scope="book",
                    scene_id=None,
                    category="romance_arc",
                    severity=4,
                    signal="no_active_intimacy_pairs",
                    evidence="Dashboard summary has no tracked intimacy pair state.",
                    recommendation=(
                        "Confirm the protagonist pair is tracked and that first touch/charged "
                        "moment/kiss beats are distinguishable."
                    ),
                    source=self.reviewer_id,
                )
            )
        return issues


class CharacterArcReviewer(BaseBookReviewer):
    def __init__(self) -> None:
        super().__init__(reviewer_id="character_arc_reviewer")

    def review(self, context: BookRunContext) -> list[RevisionIssue]:
        if context.narrative_counts.get("character_arc", 0) > 0:
            return []
        return [
            RevisionIssue(
                scope="book",
                scene_id=None,
                category="character_arc",
                severity=5,
                signal="no_character_arc_events",
                evidence="CharacterArcLedger has no runtime events.",
                recommendation=(
                    "Populate character arc events during scene finalization, then revise "
                    "scenes with missing wound/belief movement."
                ),
                source=self.reviewer_id,
            )
        ]


class ContinuityAndPromiseReviewer(BaseBookReviewer):
    def __init__(self) -> None:
        super().__init__(reviewer_id="continuity_promise_reviewer")

    def review(self, context: BookRunContext) -> list[RevisionIssue]:
        issues: list[RevisionIssue] = []
        if context.narrative_counts.get("promise", 0) == 0:
            issues.append(
                RevisionIssue(
                    scope="book",
                    scene_id=None,
                    category="promise_ledger",
                    severity=4,
                    signal="no_promise_events",
                    evidence="PromiseLedger has no opened/progressed/resolved promise events.",
                    recommendation=(
                        "Extract narrative questions, obligations, and foreshadowing events "
                        "so overdue promise checks become meaningful."
                    ),
                    source=self.reviewer_id,
                )
            )
        if int(context.ledger_dashboard.get("promises_critical_open", 0)) > 0:
            issues.append(
                RevisionIssue(
                    scope="book",
                    scene_id=None,
                    category="promise_ledger",
                    severity=5,
                    signal="critical_promises_open",
                    evidence=(
                        "Critical open promises: "
                        f"{context.ledger_dashboard.get('promises_critical_open')}"
                    ),
                    recommendation=(
                        "Resolve or explicitly carry critical promises before final "
                        "editorial review."
                    ),
                    source=self.reviewer_id,
                )
            )
        if context.narrative_counts.get("subplot", 0) == 0:
            issues.append(
                RevisionIssue(
                    scope="book",
                    scene_id=None,
                    category="subplot_ledger",
                    severity=3,
                    signal="no_subplot_events",
                    evidence="SubplotLedger has no runtime events.",
                    recommendation=(
                        "Track professional/family/external subplot movement for book-level "
                        "revision targeting."
                    ),
                    source=self.reviewer_id,
                )
            )
        return issues


class CommercialReadabilityReviewer(BaseBookReviewer):
    def __init__(self) -> None:
        super().__init__(reviewer_id="commercial_readability_reviewer")

    def review(self, context: BookRunContext) -> list[RevisionIssue]:
        issues: list[RevisionIssue] = []
        for scene in context.scenes:
            if scene.eval_ai_tell is not None and scene.eval_ai_tell < 0.65:
                issues.append(
                    _scene_issue(
                        scene,
                        category="ai_tell_density",
                        severity=4,
                        signal="low_ai_tell_eval_score",
                        evidence=f"AI-tell score {scene.eval_ai_tell:.4f} is below 0.65.",
                        recommendation=(
                            "Line-edit for repeated abstractions, explanatory prose, and "
                            "summary emotion labels."
                        ),
                        source=self.reviewer_id,
                    )
                )
            weighted = scene.quality_scores.get("structural_weighted_points")
            metric_words = scene.quality_scores.get("metric_word_count") or scene.status_word_count
            if weighted is not None and metric_words > 0:
                weighted_per_1k = weighted / metric_words * 1000
                if weighted_per_1k > 4.5:
                    issues.append(
                        _scene_issue(
                            scene,
                            category="structural_density",
                            severity=3,
                            signal="high_weighted_structural_density",
                            evidence=(
                                "Weighted structural density is "
                                f"{weighted_per_1k:.2f} per 1K words."
                            ),
                            recommendation=(
                                "Prioritize this scene for structural cleanup before broad "
                                "prose polish."
                            ),
                            source=self.reviewer_id,
                            metadata={"weighted_per_1k": round(weighted_per_1k, 4)},
                        )
                    )
            dialogue_ratio = _metric_float(scene, "dialogue_ratio")
            if dialogue_ratio is not None and dialogue_ratio < 0.15:
                issues.append(
                    _scene_issue(
                        scene,
                        category="dialogue_balance",
                        severity=2,
                        signal="low_dialogue_ratio",
                        evidence=f"Dialogue ratio {dialogue_ratio:.3f} is below 0.15.",
                        recommendation=(
                            "Consider adding conflict-bearing dialogue if the scene reads static."
                        ),
                        source=self.reviewer_id,
                    )
                )

        for phrase, scene_ids in context.repeated_phrases.items():
            issues.append(
                RevisionIssue(
                    scope="book",
                    scene_id=None,
                    category="repeated_phrase",
                    severity=3 if len(scene_ids) < 8 else 4,
                    signal="repeated_phrase_across_book",
                    evidence=f"Phrase '{phrase}' appears in {len(scene_ids)} scenes.",
                    recommendation=(
                        "Vary or cut repeated phrasing during line edit; inspect listed "
                        "scenes first."
                    ),
                    source=self.reviewer_id,
                    metadata={"phrase": phrase, "scene_ids": list(scene_ids)},
                )
            )
        return issues


def default_book_reviewers() -> list[BaseBookReviewer]:
    return [
        BookPacingReviewer(),
        RomanceArcReviewer(),
        CharacterArcReviewer(),
        ContinuityAndPromiseReviewer(),
        CommercialReadabilityReviewer(),
    ]


def _scene_issue(
    scene: AnalyzedScene,
    *,
    category: str,
    severity: int,
    signal: str,
    evidence: str,
    recommendation: str,
    source: str,
    metadata: dict[str, object] | None = None,
) -> RevisionIssue:
    return RevisionIssue(
        scope="scene",
        scene_id=scene.scene_id,
        chapter_id=scene.chapter_id,
        category=category,
        severity=severity,
        signal=signal,
        evidence=evidence,
        recommendation=recommendation,
        source=source,
        metadata=metadata or {},
    )


def _metric_float(scene: AnalyzedScene, key: str) -> float | None:
    value = scene.metrics.get(key)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None
