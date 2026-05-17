"""Unit tests for ConvergenceController (Task 007)."""

from __future__ import annotations

from pathlib import Path

from pipeline.agents.agent_models import QualityResult
from pipeline.convergence_controller import ConvergenceController, ConvergenceDecision
from pipeline.core.job_context import JobContext
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)


def _make_spec(max_heat: float = 5.0) -> ProjectSpec:
    return ProjectSpec(
        book_id="test-book",
        series_id="test-series",
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(genre_name="romance"),
        sensitivity_thresholds=ResolvedSensitivityThresholds(max_heat_level=max_heat),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )


def _make_jc(heat_level: int = 1, **kwargs: object) -> JobContext:
    return JobContext(
        job_id="j1",
        series_id="s1",
        book_id="b1",
        chapter_id=1,
        scene_id="ch01_sc01",
        spec=_make_spec(),
        heat_level=heat_level,
        **kwargs,  # type: ignore[arg-type]
    )


class TestConvergenceControllerGo:
    def test_go_when_quality_passes(self) -> None:
        ctrl = ConvergenceController()
        qr = QualityResult(needs_review=False, tier="pass")
        decision = ctrl.decide(qr, _make_jc())
        assert decision == ConvergenceDecision.GO

    def test_go_on_warn_tier(self) -> None:
        ctrl = ConvergenceController()
        qr = QualityResult(needs_review=False, tier="warn")
        assert ctrl.decide(qr, _make_jc()) == ConvergenceDecision.GO


class TestConvergenceControllerRevise:
    def test_revise_on_needs_review_under_limit(self) -> None:
        ctrl = ConvergenceController(max_revisions=3)
        qr = QualityResult(needs_review=True, tier="fail")
        assert ctrl.decide(qr, _make_jc(), revise_count=0) == ConvergenceDecision.REVISE
        assert ctrl.decide(qr, _make_jc(), revise_count=2) == ConvergenceDecision.REVISE

    def test_re_plan_when_max_revisions_exhausted(self) -> None:
        ctrl = ConvergenceController(max_revisions=3)
        qr = QualityResult(needs_review=True, tier="fail")
        assert ctrl.decide(qr, _make_jc(), revise_count=3) == ConvergenceDecision.RE_PLAN


class TestConvergenceControllerSensitivity:
    def test_re_plan_on_sensitivity_violation(self) -> None:
        """Sensitivity violation → RE_PLAN, never FORCE_RESOLVE (DEC-005)."""
        ctrl = ConvergenceController()
        qr = QualityResult(needs_review=False, tier="pass", sensitivity_violation=True)
        decision = ctrl.decide(qr, _make_jc())
        assert decision == ConvergenceDecision.RE_PLAN
        assert decision.value != ConvergenceDecision.FORCE_RESOLVE.value

    def test_re_plan_overrides_budget_exhaustion(self) -> None:
        """Sensitivity check runs before budget check."""
        ctrl = ConvergenceController(budget_words_threshold=999999)
        qr = QualityResult(needs_review=False, sensitivity_violation=True)
        jc = _make_jc()
        jc = jc.with_output("quality_agent", {"word_count_remaining": 0})
        assert ctrl.decide(qr, jc) == ConvergenceDecision.RE_PLAN


class TestConvergenceControllerForceResolve:
    def test_force_resolve_on_budget_exhaustion_writes_log(self, tmp_path: Path) -> None:
        log_path = tmp_path / "decisions.jsonl"
        ctrl = ConvergenceController(budget_words_threshold=0, decisions_log_path=log_path)
        qr = QualityResult(needs_review=False, tier="pass")
        jc = _make_jc().with_output("quality_agent", {"word_count_remaining": 0})
        decision = ctrl.decide(qr, jc)
        assert decision == ConvergenceDecision.FORCE_RESOLVE
        assert log_path.exists()
        import json

        entry = json.loads(log_path.read_text().strip())
        assert entry["event"] == "FORCE_RESOLVE"
        assert "scene_id" in entry


class TestConvergenceControllerBibleContradiction:
    def test_bible_contradiction_routes_to_re_plan(self) -> None:
        ctrl = ConvergenceController()
        qr = QualityResult(needs_review=False, tier="pass")
        jc = JobContext(
            job_id="j1",
            series_id="s1",
            book_id="b1",
            chapter_id=1,
            scene_id="ch01_sc01",
            spec=_make_spec(),
            bible_contradiction=True,
        )
        assert ctrl.decide(qr, jc) == ConvergenceDecision.RE_PLAN
