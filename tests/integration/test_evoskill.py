"""Integration tests — EvoSkill (Task 012).

Tests:
  1. trace_collector_failure_classification — bible_contradiction → failure/continuity_error
  2. trace_collector_success_classification — clean context/GO → success
  3. evoskill_propose_stub — no api_url; propose returns CandidateSkill
  4. evoskill_frontier_kept — improvement > 0; update_frontier returns True
  5. skill_promoter_local_write — promote_to_wiki writes data/{series_id}/skills/{skill_id}.md
  6. series_namespace_isolation — traces saved for A not returned for B
  7. full_nightly_flow — fixture failure trace → propose → evaluate → frontier → promote
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pipeline.core.job_context import JobContext
from pipeline.evoskill.evoskill_client import CandidateSkill, EvoSkillClient
from pipeline.evoskill.skill_promoter import SkillPromoter
from pipeline.evoskill.trace_collector import Trace, TraceCollector
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_spec() -> ProjectSpec:
    return ProjectSpec(
        book_id="book-001",
        series_id="series-A",
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(),
        sensitivity_thresholds=ResolvedSensitivityThresholds(),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )


def _make_job(
    series_id: str = "series-A",
    scene_id: str = "scene-001",
    book_id: str = "book-001",
    bible_contradiction: bool = False,
    overdue_promises: list[str] | None = None,
    final_text: str = "The quick brown fox jumped over the lazy dog.",
) -> JobContext:
    return JobContext(
        job_id="job-test-001",
        series_id=series_id,
        book_id=book_id,
        chapter_id=1,
        scene_id=scene_id,
        spec=_make_spec(),
        bible_contradiction=bible_contradiction,
        overdue_promises=overdue_promises or [],
        final_text=final_text,
    )


def _make_failure_trace(
    series_id: str = "series-A",
    scene_id: str = "scene-001",
    failure_mode: str = "quality_gate_fail",
) -> Trace:
    return Trace(
        trace_id="trace-fixture-001",
        series_id=series_id,
        book_id="book-001",
        scene_id=scene_id,
        trace_type="failure",
        failure_mode=failure_mode,
        agent_inputs={},
        agent_outputs={},
        routing_decisions=["REVISE"],
        quality_scores={},
        critic_scores={},
        word_count=50,
        timestamp=datetime.now(UTC).isoformat(),
    )


# ── Test 1: failure classification — bible_contradiction ──────────────────────


def test_trace_collector_failure_classification(tmp_path: Path) -> None:
    """JobContext with bible_contradiction=True yields failure/continuity_error."""
    collector = TraceCollector(data_root=tmp_path / "data")
    job = _make_job(bible_contradiction=True)

    trace = collector.collect_scene_trace(
        job_context=job,
        routing_decisions=["GO"],
    )

    assert trace.trace_type == "failure"
    assert trace.failure_mode == "continuity_error"
    assert trace.series_id == "series-A"
    assert trace.scene_id == "scene-001"


# ── Test 2: success classification ────────────────────────────────────────────


def test_trace_collector_success_classification(tmp_path: Path) -> None:
    """Clean JobContext with routing_decisions=['GO'] yields success trace."""
    collector = TraceCollector(data_root=tmp_path / "data")
    job = _make_job(
        bible_contradiction=False,
        overdue_promises=[],
        final_text="Hero meets villain. Conflict ensues. Resolution achieved.",
    )

    trace = collector.collect_scene_trace(
        job_context=job,
        routing_decisions=["GO"],
    )

    assert trace.trace_type == "success"
    assert trace.failure_mode is None
    # ["Hero", "meets", "villain.", "Conflict", "ensues.", "Resolution", "achieved."]
    assert trace.word_count == 7


# ── Test 3: propose_skill in stub mode ───────────────────────────────────────


def test_evoskill_propose_stub() -> None:
    """No api_url → propose_skill returns a CandidateSkill without network calls."""
    client = EvoSkillClient(api_url=None, api_key=None)
    failure_trace = _make_failure_trace(failure_mode="quality_gate_fail")

    candidate = client.propose_skill([failure_trace], series_id="series-A")

    assert isinstance(candidate, CandidateSkill)
    assert candidate.series_id == "series-A"
    assert candidate.skill_id  # non-empty UUID
    assert candidate.failure_mode == "quality_gate_fail"
    assert candidate.condition
    assert candidate.recommendation
    assert candidate.proposed_at


# ── Test 4: frontier kept when improvement > 0 ───────────────────────────────


def test_evoskill_frontier_kept() -> None:
    """EvalResult with improvement > 0 → update_frontier returns True (mock mode)."""
    client = EvoSkillClient(api_url=None, api_key=None)
    failure_trace = _make_failure_trace()
    candidate = client.propose_skill([failure_trace], series_id="series-A")
    eval_result = client.evaluate_skill(candidate, [failure_trace])

    assert eval_result.improvement > 0
    kept = client.update_frontier(candidate, eval_result)
    assert kept is True


# ── Test 5: SkillPromoter local write ────────────────────────────────────────


def test_skill_promoter_local_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """promote_to_wiki (no wuphf_client) writes skill markdown to disk."""
    # Redirect Path("data") to tmp_path/data via monkeypatching working dir.
    monkeypatch.chdir(tmp_path)

    promoter = SkillPromoter(wuphf_client=None)
    skill = CandidateSkill(
        skill_id="skill-abc123",
        series_id="series-A",
        condition="quality score below threshold",
        recommendation="inject bible summary",
        failure_mode="quality_gate_fail",
        proposed_at=datetime.now(UTC).isoformat(),
        score=0.7,
    )

    promoter.promote_to_wiki(skill, series_id="series-A")

    dest = tmp_path / "data" / "series-A" / "skills" / "skill-abc123.md"
    assert dest.exists(), f"Expected {dest} to exist after promote_to_wiki"
    content = dest.read_text(encoding="utf-8")
    assert "# Skill: skill-abc123" in content
    assert "## Condition" in content
    assert "## Recommendation" in content
    assert "quality score below threshold" in content
    assert "inject bible summary" in content


# ── Test 6: series namespace isolation ───────────────────────────────────────


def test_series_namespace_isolation(tmp_path: Path) -> None:
    """Traces saved for series-A are not returned by get_failure_traces for series-B."""
    data_root = tmp_path / "data"
    collector = TraceCollector(data_root=data_root)

    job_a = _make_job(series_id="series-A", scene_id="scene-001", bible_contradiction=True)
    trace_a = collector.collect_scene_trace(job_a, routing_decisions=["RE_PLAN"])
    collector.save_trace(trace_a)

    # series-B has no traces at all
    failures_b = collector.get_failure_traces("series-B")
    assert failures_b == []

    # series-A returns the saved trace
    failures_a = collector.get_failure_traces("series-A")
    assert len(failures_a) == 1
    assert failures_a[0].series_id == "series-A"


# ── Test 7: full nightly flow ─────────────────────────────────────────────────


def test_full_nightly_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: fixture failure trace → propose → evaluate → frontier → promote."""
    monkeypatch.chdir(tmp_path)
    data_root = tmp_path / "data"

    # Seed a failure trace
    collector = TraceCollector(data_root=data_root)
    job = _make_job(
        series_id="series-full",
        scene_id="scene-nightly",
        bible_contradiction=True,
    )
    trace = collector.collect_scene_trace(job, routing_decisions=["RE_PLAN"])
    collector.save_trace(trace)

    # Verify it was persisted
    saved = collector.get_failure_traces("series-full")
    assert len(saved) == 1

    # Propose
    client = EvoSkillClient(api_url=None, api_key=None)
    candidate = client.propose_skill(saved, series_id="series-full")
    assert candidate.series_id == "series-full"

    # Evaluate
    eval_result = client.evaluate_skill(candidate, saved)
    assert eval_result.passed

    # Update frontier
    kept = client.update_frontier(candidate, eval_result)
    assert kept

    # Promote
    promoter = SkillPromoter(wuphf_client=None)
    promoter.promote_to_wiki(candidate, series_id="series-full")

    skill_file = tmp_path / "data" / "series-full" / "skills" / f"{candidate.skill_id}.md"
    assert skill_file.exists(), f"Promoted skill file not found at {skill_file}"
    md = skill_file.read_text(encoding="utf-8")
    assert f"# Skill: {candidate.skill_id}" in md
