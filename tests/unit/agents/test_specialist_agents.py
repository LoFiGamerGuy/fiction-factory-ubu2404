"""Unit tests for all 9 specialist agents (Task 008)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from pipeline.agents.agent_models import EditorOutput
from pipeline.agents.arc_reader_agent import ArcReaderAgent, ArcReaderOutput
from pipeline.agents.arc_reader_packet_agent import ArcReaderPacketAgent
from pipeline.agents.copy_editor_agent import CopyEditorAgent
from pipeline.agents.developmental_editor_agent import DevelopmentalEditorAgent
from pipeline.agents.drift_detector_agent import DriftDetectorAgent, DriftDetectorOutput
from pipeline.agents.genre_norm_editor_agent import GenreNormEditorAgent
from pipeline.agents.line_editor_agent import LineEditorAgent
from pipeline.agents.proofreader_agent import ProofreaderAgent
from pipeline.agents.revision_agent import RevisionAgent, RevisionOutput
from pipeline.core.job_context import JobContext
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)


def _make_spec(genre: str = "romance") -> ProjectSpec:
    return ProjectSpec(
        book_id="test-book",
        series_id="test-series",
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(genre_name=genre),
        sensitivity_thresholds=ResolvedSensitivityThresholds(max_heat_level=5.0),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )


def _make_agent_ctx(tmp_path: Path) -> Any:
    from pipeline.core.agent_context import AgentContext
    from pipeline.core.project_layout import ProjectLayout

    layout = ProjectLayout(series_root=tmp_path / "series", book_id="test-book")
    ledger = LedgerManager(book_id="test-book", data_root=tmp_path / "data")
    spec_loader_mock = MagicMock()
    spec_loader_mock.load.side_effect = lambda *_: {
        "profile_id": "romance_module_v1",
        "version": "1.0",
        "heat_curve": "rising",
        "scene_function_vocabulary": [
            "meet_cute",
            "inciting_incident",
            "black_moment",
            "resolution",
        ],
        "required_scene_slots": [],
    }
    return AgentContext(
        project_layout=layout,
        spec_loader=spec_loader_mock,
        ledger_manager=ledger,
        log_path=tmp_path / "agent.log",
        output_dir=tmp_path / "output",
        model_tier="test",
    )


def _make_jc(tmp_path: Path, scene_id: str = "ch01_sc01", **kwargs: Any) -> JobContext:
    jc = JobContext(
        job_id="j1",
        series_id="s1",
        book_id="test-book",
        chapter_id=1,
        scene_id=scene_id,
        spec=_make_spec(),
        scene_brief="Two people meet.",
        **kwargs,
    )
    return jc.with_output(
        "editor_agent",
        EditorOutput(
            edited_text="She walked into the shop. The rain fell hard.",
            nofly_violations=0,
            structural_flags=0,
            is_clean=True,
        ).model_dump(),
    )


def _mock_router(output_model: type) -> MagicMock:
    router = MagicMock()
    router.call.return_value = output_model()
    return router


class TestArcReaderAgent:
    def test_instantiates_and_runs(self, tmp_path: Path) -> None:
        ctx = _make_agent_ctx(tmp_path)
        router = MagicMock()
        router.call.return_value = ArcReaderOutput(arc_momentum="advancing")
        agent = ArcReaderAgent(ctx=ctx, model_router=router)
        result = agent.run(_make_jc(tmp_path))
        assert "arc_reader_agent" in result.output_data
        assert result.output_data["arc_reader_agent"]["arc_momentum"] == "advancing"


class TestArcReaderPacketAgent:
    def test_instantiates_and_runs(self, tmp_path: Path) -> None:
        from pipeline.agents.arc_reader_packet_agent import ArcReaderPacketOutput

        ctx = _make_agent_ctx(tmp_path)
        router = MagicMock()
        router.call.return_value = ArcReaderPacketOutput(overall_arc_health="healthy")
        agent = ArcReaderPacketAgent(ctx=ctx, model_router=router)
        result = agent.run(_make_jc(tmp_path))
        assert "arc_reader_packet_agent" in result.output_data


class TestDriftDetectorAgent:
    def test_no_drift_detected(self, tmp_path: Path) -> None:
        ctx = _make_agent_ctx(tmp_path)
        router = MagicMock()
        router.call.return_value = DriftDetectorOutput(drift_detected=False)
        agent = DriftDetectorAgent(ctx=ctx, model_router=router)
        result = agent.run(_make_jc(tmp_path))
        assert not result.output_data["drift_detector_agent"]["drift_detected"]

    def test_drift_detected(self, tmp_path: Path) -> None:
        ctx = _make_agent_ctx(tmp_path)
        router = MagicMock()
        router.call.return_value = DriftDetectorOutput(
            drift_detected=True, drift_axes=["interiority"]
        )
        agent = DriftDetectorAgent(ctx=ctx, model_router=router)
        result = agent.run(_make_jc(tmp_path))
        assert result.output_data["drift_detector_agent"]["drift_detected"] is True


class TestDevelopmentalEditorAgent:
    def test_instantiates_and_runs(self, tmp_path: Path) -> None:
        from pipeline.agents.developmental_editor_agent import DevelopmentalEditorOutput

        ctx = _make_agent_ctx(tmp_path)
        router = MagicMock()
        router.call.return_value = DevelopmentalEditorOutput(revised_text="Revised.")
        agent = DevelopmentalEditorAgent(ctx=ctx, model_router=router)
        result = agent.run(_make_jc(tmp_path))
        assert "developmental_editor_agent" in result.output_data


class TestLineEditorAgent:
    def test_instantiates_and_runs(self, tmp_path: Path) -> None:
        from pipeline.agents.line_editor_agent import LineEditorOutput

        ctx = _make_agent_ctx(tmp_path)
        router = MagicMock()
        router.call.return_value = LineEditorOutput(polished_text="Polished.")
        agent = LineEditorAgent(ctx=ctx, model_router=router)
        result = agent.run(_make_jc(tmp_path))
        assert "line_editor_agent" in result.output_data


class TestCopyEditorAgent:
    def test_instantiates_and_runs(self, tmp_path: Path) -> None:
        from pipeline.agents.copy_editor_agent import CopyEditorOutput

        ctx = _make_agent_ctx(tmp_path)
        router = MagicMock()
        router.call.return_value = CopyEditorOutput(corrected_text="Corrected.")
        agent = CopyEditorAgent(ctx=ctx, model_router=router)
        result = agent.run(_make_jc(tmp_path))
        assert "copy_editor_agent" in result.output_data


class TestProofreaderAgent:
    def test_instantiates_and_runs(self, tmp_path: Path) -> None:
        from pipeline.agents.proofreader_agent import ProofreaderOutput

        ctx = _make_agent_ctx(tmp_path)
        router = MagicMock()
        router.call.return_value = ProofreaderOutput(proofread_text="Final.", is_clean=True)
        agent = ProofreaderAgent(ctx=ctx, model_router=router)
        result = agent.run(_make_jc(tmp_path))
        assert result.output_data["proofreader_agent"]["is_clean"] is True


class TestRevisionAgent:
    def test_instantiates_and_runs(self, tmp_path: Path) -> None:
        ctx = _make_agent_ctx(tmp_path)
        router = MagicMock()
        router.call.return_value = RevisionOutput(revised_text="Better version.")
        agent = RevisionAgent(ctx=ctx, model_router=router)
        result = agent.run(_make_jc(tmp_path))
        assert result.output_data["revision_agent"]["revised_text"] == "Better version."


class TestGenreNormEditorAgent:
    def test_valid_scene_passes(self, tmp_path: Path) -> None:
        ctx = _make_agent_ctx(tmp_path)
        agent = GenreNormEditorAgent(ctx=ctx)
        jc = _make_jc(tmp_path).with_output("_scene_function", {"value": "meet_cute"})
        # patch scene_function lookup
        jc = JobContext(
            job_id="j1",
            series_id="s1",
            book_id="test-book",
            chapter_id=1,
            scene_id="ch01_sc01",
            spec=_make_spec(),
            heat_level=1,
            output_data={
                "_scene_function": "meet_cute",
                "editor_agent": {"edited_text": "They met.", "nofly_violations": 0},
            },
        )
        result = agent.run(jc)
        data = result.output_data["genre_norm_editor_agent"]
        assert data["passed"] is True

    def test_heat_curve_violation_at_opening_chapter(self, tmp_path: Path) -> None:
        """Scene at position 0.03 with heat_level=4 violates Romance 'rising' curve."""
        ctx = _make_agent_ctx(tmp_path)
        agent = GenreNormEditorAgent(ctx=ctx)
        jc = JobContext(
            job_id="j1",
            series_id="s1",
            book_id="test-book",
            chapter_id=1,  # position ≈ 0.03 of 30-chapter book
            scene_id="ch01_sc01",
            spec=_make_spec(),
            heat_level=4,  # too high for position 0.03 on rising curve (max=2)
            output_data={"editor_agent": {"edited_text": "Hot scene.", "nofly_violations": 0}},
        )
        result = agent.run(jc)
        data = result.output_data["genre_norm_editor_agent"]
        assert data["passed"] is False
        violation_types = [v["violation_type"] for v in data["violations"]]
        assert "heat_curve" in violation_types
