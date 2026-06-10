"""JobRunner Phase 9 continuity integration tests."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

from pipeline.agents.agent_models import EditorOutput, QualityResult, WriterOutput
from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
from pipeline.core.project_layout import ProjectLayout
from pipeline.job_runner import JobRunner
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)
from pipeline.scene_state_machine import SceneState


def _make_spec() -> ProjectSpec:
    return ProjectSpec(
        book_id="book1",
        series_id="series1",
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(genre_name="romance"),
        sensitivity_thresholds=ResolvedSensitivityThresholds(),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )


def _make_context(tmp_path: Path) -> AgentContext:
    return AgentContext(
        project_layout=ProjectLayout(series_root=tmp_path / "series", book_id="book1"),
        spec_loader=MagicMock(),
        ledger_manager=LedgerManager(book_id="book1", series_id="series1", data_root=tmp_path),
        log_path=tmp_path / "agent.log",
        output_dir=tmp_path / "output",
        model_tier="test",
    )


def _make_job() -> JobContext:
    return JobContext(
        job_id="job1",
        series_id="series1",
        book_id="book1",
        chapter_id=1,
        scene_id="ch01_sc01",
        spec=_make_spec(),
        scene_brief="A clean scene.",
    )


def _patch_agents(monkeypatch: Any, continuity_mode: str) -> list[Any]:
    continuity_instances: list[Any] = []

    class FakeWriter:
        def __init__(self, ctx: AgentContext, model_router: object) -> None:
            pass

        def run(self, jc: JobContext) -> JobContext:
            return jc.with_output(
                "writer_agent",
                WriterOutput(
                    draft_text="Clean draft.", word_count=2, scene_id=jc.scene_id
                ).model_dump(),
            )

    class FakeEditor:
        def __init__(self, ctx: AgentContext, model_router: object) -> None:
            pass

        def run(self, jc: JobContext) -> JobContext:
            return jc.with_output(
                "editor_agent",
                EditorOutput(edited_text="Clean edited scene.").model_dump(),
            )

    class FakeQuality:
        def __init__(self, ctx: AgentContext) -> None:
            self.update_ledgers = MagicMock()

        def run(self, jc: JobContext) -> JobContext:
            return jc.with_output(
                "quality_agent",
                QualityResult(needs_review=False, tier="pass", scene_id=jc.scene_id).model_dump(),
            )

    class FakeContinuity:
        def __init__(self, **kwargs: object) -> None:
            self.commit_approved_changes = MagicMock()
            continuity_instances.append(self)

        def run(self, jc: JobContext) -> JobContext:
            if continuity_mode == "contradiction":
                return dataclasses.replace(jc, bible_contradiction=True)
            if continuity_mode == "overdue":
                return dataclasses.replace(jc, overdue_promises=["p001"])
            return jc

    monkeypatch.setattr("pipeline.job_runner.WriterAgent", FakeWriter)
    monkeypatch.setattr("pipeline.agents.editor_agent.EditorAgent", FakeEditor)
    monkeypatch.setattr("pipeline.job_runner.QualityAgent", FakeQuality)
    monkeypatch.setattr("pipeline.job_runner.ContinuityAgent", FakeContinuity)
    return continuity_instances


def test_job_runner_routes_bible_contradiction_to_re_plan(tmp_path: Path, monkeypatch: Any) -> None:
    continuity_instances = _patch_agents(monkeypatch, "contradiction")
    runner = JobRunner(agent_ctx=_make_context(tmp_path), model_router=MagicMock(), max_revisions=1)

    result = runner.run_scene(_make_job())

    assert result.convergence_decision == "RE_PLAN"
    assert result.force_resolved is True
    assert result.final_state["bible_contradiction"] is True
    continuity_instances[0].commit_approved_changes.assert_not_called()


def test_job_runner_routes_overdue_promises_to_revise_then_re_plan(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    continuity_instances = _patch_agents(monkeypatch, "overdue")
    runner = JobRunner(agent_ctx=_make_context(tmp_path), model_router=MagicMock(), max_revisions=1)

    result = runner.run_scene(_make_job())

    assert result.convergence_decision == "RE_PLAN"
    assert result.revise_count == 1
    assert result.final_state["overdue_promises"] == ["p001"]
    continuity_instances[0].commit_approved_changes.assert_not_called()


def test_job_runner_commits_continuity_on_go(tmp_path: Path, monkeypatch: Any) -> None:
    continuity_instances = _patch_agents(monkeypatch, "clean")
    runner = JobRunner(agent_ctx=_make_context(tmp_path), model_router=MagicMock(), max_revisions=1)

    result = runner.run_scene(_make_job())

    assert result.convergence_decision == "GO"
    continuity_instances[0].commit_approved_changes.assert_called_once()


def test_job_runner_collects_evoskill_trace_on_completion(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Phase 12: JobRunner saves EvoSkill trace after scene completion (success path)."""
    from pipeline.evoskill.trace_collector import TraceCollector

    _patch_agents(monkeypatch, "clean")

    data_root = tmp_path / "data"
    trace_collector = TraceCollector(data_root=data_root)

    runner = JobRunner(
        agent_ctx=_make_context(tmp_path),
        model_router=MagicMock(),
        max_revisions=1,
        trace_collector=trace_collector,
    )

    result = runner.run_scene(_make_job())

    assert result.convergence_decision == "GO"

    # Verify trace was saved to disk
    trace_path = data_root / "series1" / "traces" / "ch01_sc01.json"
    assert trace_path.exists(), f"Expected trace at {trace_path}"

    # Verify trace content
    import json

    saved_trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert saved_trace["series_id"] == "series1"
    assert saved_trace["scene_id"] == "ch01_sc01"
    assert saved_trace["trace_type"] == "success"
    assert saved_trace["failure_mode"] is None
    assert "GO" in saved_trace["routing_decisions"]


def test_job_runner_collects_failure_trace_on_contradiction(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Phase 12: JobRunner saves failure trace when bible_contradiction occurs."""
    from pipeline.evoskill.trace_collector import TraceCollector

    _patch_agents(monkeypatch, "contradiction")

    data_root = tmp_path / "data"
    trace_collector = TraceCollector(data_root=data_root)

    runner = JobRunner(
        agent_ctx=_make_context(tmp_path),
        model_router=MagicMock(),
        max_revisions=1,
        trace_collector=trace_collector,
    )

    result = runner.run_scene(_make_job())

    assert result.convergence_decision == "RE_PLAN"

    # Verify failure trace was saved
    trace_path = data_root / "series1" / "traces" / "ch01_sc01.json"
    assert trace_path.exists()

    import json

    saved_trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert saved_trace["trace_type"] == "failure"
    assert saved_trace["failure_mode"] == "continuity_error"


def test_job_runner_trace_marks_revised_go_as_failure(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Phase 12: a final GO after REVISE is still a failure trace for EvoSkill."""
    from pipeline.evoskill.trace_collector import TraceCollector

    _patch_agents(monkeypatch, "clean")

    data_root = tmp_path / "data"
    trace_collector = TraceCollector(data_root=data_root)
    runner = JobRunner(
        agent_ctx=_make_context(tmp_path),
        model_router=MagicMock(),
        max_revisions=1,
        trace_collector=trace_collector,
    )
    final_state: dict[str, Any] = {
        "convergence_decision": "GO",
        "revise_count": 1,
        "final_text": "Clean edited scene.",
        "bible_contradiction": False,
        "overdue_promises": [],
        "writer_output": {},
        "editor_output": {},
        "quality_output": {"tier": "pass", "needs_review": False},
    }

    runner._collect_trace_safe(_make_job(), cast(SceneState, final_state))  # noqa: SLF001

    import json

    trace_path = data_root / "series1" / "traces" / "ch01_sc01.json"
    saved_trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert saved_trace["trace_type"] == "failure"
    assert saved_trace["failure_mode"] == "quality_gate_fail"
    assert saved_trace["routing_decisions"] == ["REVISE", "GO"]


def test_job_runner_trace_collection_failure_does_not_break_scene(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Phase 12: Trace collection failure is logged but does not break scene execution."""
    from pipeline.evoskill.trace_collector import TraceCollector

    _patch_agents(monkeypatch, "clean")

    # Create a trace collector that will fail on save
    trace_collector = TraceCollector(data_root=tmp_path / "data")

    # Monkeypatch save_trace to raise an exception
    def failing_save(trace: object) -> None:
        raise RuntimeError("Simulated trace save failure")

    monkeypatch.setattr(trace_collector, "save_trace", failing_save)

    runner = JobRunner(
        agent_ctx=_make_context(tmp_path),
        model_router=MagicMock(),
        max_revisions=1,
        trace_collector=trace_collector,
    )

    # Scene should complete successfully despite trace save failure
    result = runner.run_scene(_make_job())

    assert result.convergence_decision == "GO"
    assert result.error == ""  # Scene execution was not broken by trace failure
