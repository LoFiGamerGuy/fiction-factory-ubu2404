"""Unit tests for SceneStateMachine (Task 007)."""

from __future__ import annotations

import dataclasses
from typing import Any
from unittest.mock import MagicMock

import pytest

from pipeline.agents.agent_models import EditorOutput, QualityResult, WriterOutput
from pipeline.convergence_controller import ConvergenceController
from pipeline.core.job_context import JobContext
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)
from pipeline.scene_state_machine import SceneState, SceneStateMachine


def _make_spec() -> ProjectSpec:
    return ProjectSpec(
        book_id="test-book",
        series_id="test-series",
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(genre_name="romance"),
        sensitivity_thresholds=ResolvedSensitivityThresholds(),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )


def _make_initial_state(**kwargs: Any) -> SceneState:
    base: SceneState = {
        "job_id": "j1",
        "scene_id": "ch01_sc01",
        "book_id": "b1",
        "series_id": "s1",
        "chapter_id": 1,
        "model_tier": "test",
        "seed": 0,
        "scene_brief": "Two people meet in a bookshop.",
        "word_count_target": 1200,
        "heat_level": 1,
        "writer_output": {},
        "editor_output": {},
        "quality_output": {},
        "convergence_decision": "",
        "revise_count": 0,
        "final_text": "",
        "force_resolved": False,
        "force_resolve_reason": "",
        "bible_contradiction": False,
        "overdue_promises": [],
        "error": "",
    }
    base.update(kwargs)  # type: ignore[typeddict-item]
    return base


def _make_mock_writer(text: str = "Once upon a time...") -> MagicMock:
    m = MagicMock()
    m.run.side_effect = lambda jc: jc.with_output(
        "writer_agent",
        WriterOutput(
            draft_text=text, word_count=len(text.split()), scene_id=jc.scene_id
        ).model_dump(),
    )
    return m


def _make_mock_editor(clean: bool = True) -> MagicMock:
    m = MagicMock()
    m.run.side_effect = lambda jc: jc.with_output(
        "editor_agent",
        EditorOutput(
            edited_text=jc.output_data.get("writer_agent", {}).get("draft_text", "edited"),
            nofly_violations=0 if clean else 3,
            structural_flags=0 if clean else 2,
            is_clean=clean,
        ).model_dump(),
    )
    return m


def _make_mock_quality(needs_review: bool = False) -> MagicMock:
    m = MagicMock()
    m.run.side_effect = lambda jc: jc.with_output(
        "quality_agent",
        QualityResult(
            needs_review=needs_review,
            tier="fail" if needs_review else "pass",
            scene_id=jc.scene_id,
        ).model_dump(),
    )
    m.update_ledgers = MagicMock()
    return m


def _job_context_factory(state: SceneState) -> JobContext:
    merged: dict[str, Any] = {}
    for key in ("writer_output", "editor_output", "quality_output"):
        if state.get(key):
            agent_id = key.replace("_output", "_agent")
            merged[agent_id] = state[key]
    return JobContext(
        job_id=state["job_id"],
        series_id=state["series_id"],
        book_id=state["book_id"],
        chapter_id=state["chapter_id"],
        scene_id=state["scene_id"],
        spec=_make_spec(),
        model_tier=state["model_tier"],
        seed=state["seed"],
        scene_brief=state["scene_brief"],
        word_count_target=state["word_count_target"],
        heat_level=state["heat_level"],
        bible_contradiction=state["bible_contradiction"],
        overdue_promises=state["overdue_promises"],
        output_data=merged,
    )


class TestSceneStateMachineTransitions:
    def test_clean_run_reaches_final(self) -> None:
        """GO path: writer → editor → quality (pass) → final."""
        agents: dict[str, Any] = {
            "writer_agent": _make_mock_writer(),
            "editor_agent": _make_mock_editor(clean=True),
            "quality_agent": _make_mock_quality(needs_review=False),
        }
        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_job_context_factory,
            controller=ConvergenceController(max_revisions=1),
        )
        result = machine.run(_make_initial_state())
        assert result["final_text"] != ""
        assert result["convergence_decision"] == "GO"
        assert result["revise_count"] == 0
        assert not result["force_resolved"]

    def test_revise_cycle_increments_counter(self) -> None:
        """REVISE: quality fails once, passes on second attempt."""
        call_count = [0]

        def _quality_run(jc: JobContext) -> JobContext:
            call_count[0] += 1
            nr = call_count[0] < 2
            return jc.with_output(
                "quality_agent",
                QualityResult(needs_review=nr, tier="fail" if nr else "pass").model_dump(),
            )

        quality_mock = MagicMock()
        quality_mock.run.side_effect = _quality_run
        quality_mock.update_ledgers = MagicMock()

        agents: dict[str, Any] = {
            "writer_agent": _make_mock_writer(),
            "editor_agent": _make_mock_editor(clean=True),
            "quality_agent": quality_mock,
        }
        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_job_context_factory,
            controller=ConvergenceController(max_revisions=3),
        )
        result = machine.run(_make_initial_state())
        assert result["convergence_decision"] == "GO"
        assert result["revise_count"] >= 1

    def test_sensitivity_violation_force_resolves(self) -> None:
        """Sensitivity violation → RE_PLAN → force resolve."""
        quality_mock = MagicMock()
        quality_mock.run.side_effect = lambda jc: jc.with_output(
            "quality_agent",
            QualityResult(needs_review=False, sensitivity_violation=True).model_dump(),
        )
        quality_mock.update_ledgers = MagicMock()

        agents: dict[str, Any] = {
            "writer_agent": _make_mock_writer(),
            "editor_agent": _make_mock_editor(),
            "quality_agent": quality_mock,
        }
        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_job_context_factory,
            controller=ConvergenceController(max_revisions=1),
        )
        result = machine.run(_make_initial_state())
        assert result["convergence_decision"] == "RE_PLAN"
        assert result["force_resolved"] is True

    def test_max_revisions_exhausted_force_resolves(self) -> None:
        """After max REVISE attempts, route is RE_PLAN → force resolve."""
        quality_mock = MagicMock()
        quality_mock.run.side_effect = lambda jc: jc.with_output(
            "quality_agent",
            QualityResult(needs_review=True, tier="fail").model_dump(),
        )
        quality_mock.update_ledgers = MagicMock()

        agents: dict[str, Any] = {
            "writer_agent": _make_mock_writer(),
            "editor_agent": _make_mock_editor(),
            "quality_agent": quality_mock,
        }
        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_job_context_factory,
            controller=ConvergenceController(max_revisions=1),
        )
        result = machine.run(_make_initial_state())
        assert result["force_resolved"] is True

    def test_ledger_update_called_on_go(self) -> None:
        """update_ledgers should be called exactly once on GO path."""
        quality_mock = _make_mock_quality(needs_review=False)
        agents: dict[str, Any] = {
            "writer_agent": _make_mock_writer(),
            "editor_agent": _make_mock_editor(),
            "quality_agent": quality_mock,
        }
        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_job_context_factory,
        )
        machine.run(_make_initial_state())
        quality_mock.update_ledgers.assert_called_once()

    def test_approved_go_commits_continuity_changes(self) -> None:
        """Approved scenes should call approval-time continuity persistence."""
        continuity_mock = MagicMock()
        continuity_mock.run.side_effect = lambda jc: jc
        series_arc_tracker = MagicMock()

        agents: dict[str, Any] = {
            "writer_agent": _make_mock_writer(),
            "editor_agent": _make_mock_editor(),
            "continuity_agent": continuity_mock,
            "series_arc_tracker": series_arc_tracker,
            "quality_agent": _make_mock_quality(needs_review=False),
        }
        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_job_context_factory,
            controller=ConvergenceController(max_revisions=1),
        )

        result = machine.run(_make_initial_state())

        assert result["convergence_decision"] == "GO"
        continuity_mock.commit_approved_changes.assert_called_once()
        series_arc_tracker.apply_approved_updates.assert_called_once()

    def test_force_resolve_does_not_commit_continuity_changes(self) -> None:
        """RE_PLAN/FORCE_RESOLVE paths must not mutate bible or series state."""
        continuity_mock = MagicMock()
        continuity_mock.run.side_effect = lambda jc: dataclasses.replace(
            jc,
            bible_contradiction=True,
        )
        series_arc_tracker = MagicMock()

        agents: dict[str, Any] = {
            "writer_agent": _make_mock_writer(),
            "editor_agent": _make_mock_editor(),
            "continuity_agent": continuity_mock,
            "series_arc_tracker": series_arc_tracker,
            "quality_agent": _make_mock_quality(needs_review=False),
        }
        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_job_context_factory,
            controller=ConvergenceController(max_revisions=1),
        )

        result = machine.run(_make_initial_state())

        assert result["convergence_decision"] == "RE_PLAN"
        continuity_mock.commit_approved_changes.assert_not_called()
        series_arc_tracker.apply_approved_updates.assert_not_called()

    def test_series_arc_update_failure_is_fatal_in_final_node(self) -> None:
        """Series arc persistence failure should fail the scene run."""
        continuity_mock = MagicMock()
        continuity_mock.run.side_effect = lambda jc: jc
        series_arc_tracker = MagicMock()
        series_arc_tracker.apply_approved_updates.side_effect = RuntimeError("series failed")

        agents: dict[str, Any] = {
            "writer_agent": _make_mock_writer(),
            "editor_agent": _make_mock_editor(),
            "continuity_agent": continuity_mock,
            "series_arc_tracker": series_arc_tracker,
            "quality_agent": _make_mock_quality(needs_review=False),
        }
        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_job_context_factory,
            controller=ConvergenceController(max_revisions=1),
        )

        with pytest.raises(RuntimeError, match="series failed"):
            machine.run(_make_initial_state())

    def test_continuity_bible_contradiction_routes_to_re_plan(self) -> None:
        """ContinuityAgent signal should reach convergence as a RE_PLAN."""
        continuity_mock = MagicMock()
        continuity_mock.run.side_effect = lambda jc: dataclasses.replace(
            jc,
            bible_contradiction=True,
        )

        agents: dict[str, Any] = {
            "writer_agent": _make_mock_writer(),
            "editor_agent": _make_mock_editor(),
            "continuity_agent": continuity_mock,
            "quality_agent": _make_mock_quality(needs_review=False),
        }
        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_job_context_factory,
            controller=ConvergenceController(max_revisions=1),
        )
        result = machine.run(_make_initial_state())

        assert result["bible_contradiction"] is True
        assert result["convergence_decision"] == "RE_PLAN"

    def test_continuity_overdue_promises_revise_then_re_plan(self) -> None:
        """Overdue promises get one revision attempt, then route to RE_PLAN."""
        continuity_mock = MagicMock()
        continuity_mock.run.side_effect = lambda jc: dataclasses.replace(
            jc,
            overdue_promises=["p001"],
        )

        agents: dict[str, Any] = {
            "writer_agent": _make_mock_writer(),
            "editor_agent": _make_mock_editor(),
            "continuity_agent": continuity_mock,
            "quality_agent": _make_mock_quality(needs_review=False),
        }
        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_job_context_factory,
            controller=ConvergenceController(max_revisions=1),
        )
        result = machine.run(_make_initial_state())

        assert result["overdue_promises"] == ["p001"]
        assert result["revise_count"] == 1
        assert result["convergence_decision"] == "RE_PLAN"

    def test_all_scene_loop_nodes_in_graph(self) -> None:
        """Graph must contain all scene loop nodes."""
        agents: dict[str, Any] = {
            "writer_agent": _make_mock_writer(),
            "editor_agent": _make_mock_editor(),
            "quality_agent": _make_mock_quality(),
        }
        machine = SceneStateMachine(
            agents=agents,
            job_context_factory=_job_context_factory,
        )
        node_names = set(machine._graph.nodes)
        assert "writer_node" in node_names
        assert "editor_node" in node_names
        assert "continuity_node" in node_names
        assert "quality_node" in node_names
        assert "force_resolve_node" in node_names
        assert "final_node" in node_names
