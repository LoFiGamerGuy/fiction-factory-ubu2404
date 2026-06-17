"""Word-count enforcement for unattended book generation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from pipeline.agents.agent_models import WriterOutput
from pipeline.agents.editor_agent import EditorAgent
from pipeline.agents.quality_agent import QualityAgent, _classify_tier, _compute_text_metrics
from pipeline.agents.writer_agent import WriterAgent
from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
from pipeline.core.project_layout import ProjectLayout
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.ledgers.quality_evaluator import Verdict
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)
from scripts import run_full_book


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


def test_quality_agent_routes_underlength_scene_to_review(tmp_path: Path) -> None:
    ctx = _make_context(tmp_path)
    agent = QualityAgent(ctx=ctx)
    job = JobContext(
        job_id="job1",
        series_id="series1",
        book_id="book1",
        chapter_id=1,
        scene_id="scene1",
        spec=_make_spec(),
        word_count_target=100,
        output_data={
            "editor_agent": {
                "edited_text": " ".join(f"word{i}" for i in range(50)),
                "nofly_violations": 0,
                "structural_flags": 0,
            }
        },
    )

    result = agent.run(job)
    quality = result.output_data["quality_agent"]

    assert quality["needs_review"] is True
    assert quality["tier"] == "fail"
    assert any("word_count_under_target" in note for note in quality["notes"])
    assert any("at least 90 words" in note for note in quality["notes"])
    ctx.ledger_manager.close()


def test_writer_revision_prompt_includes_word_count_feedback() -> None:
    messages = WriterAgent._build_messages(
        scene_brief="Sarah confronts Miles at the harbor.",
        word_target=100,
        context_bundle_dict={},
        prior_feedback=[
            "word_count_under_target: scene has 50 words; expand to at least 90 words (target 100)."
        ],
        previous_draft="Sarah stood by the water. Miles arrived.",
    )

    prompt = messages[1]["content"]

    assert "Target length: 100 words" in prompt
    assert "Minimum acceptable length: 90 words" in prompt
    assert "## Revision Feedback" in prompt
    assert "word_count_under_target" in prompt
    assert "## Previous Draft To Expand" in prompt
    assert "Previous draft actual length: 7 words" in prompt
    assert "Add at least 83 words" in prompt
    assert "Sarah stood by the water" in prompt
    assert "no Markdown separators" in messages[0]["content"]
    assert "do not append" in prompt


def test_writer_recomputes_model_reported_word_count(tmp_path: Path) -> None:
    ctx = _make_context(tmp_path)

    class FakeRouter:
        def call(self, **_: object) -> WriterOutput:
            return WriterOutput(
                draft_text=" ".join(f"word{i}" for i in range(50)),
                word_count=1300,
                scene_id="wrong_scene",
            )

    agent = WriterAgent(ctx=ctx, model_router=FakeRouter())  # type: ignore[arg-type]
    job = JobContext(
        job_id="job1",
        series_id="series1",
        book_id="book1",
        chapter_id=1,
        scene_id="scene1",
        spec=_make_spec(),
        word_count_target=100,
        scene_brief="Test scene.",
    )

    result = agent.run(job)
    writer_output = result.output_data["writer_agent"]

    assert writer_output["word_count"] == 50
    assert writer_output["scene_id"] == "scene1"
    ctx.ledger_manager.close()


def test_full_book_run_fails_when_any_scene_force_resolves() -> None:
    assert (
        run_full_book.run_passed(
            generation_passed=True,
            force_resolved_scenes=1,
            eval_status={"passed": True},
            verifier_status={"passed": True},
            dashboard_api_status={"passed": True},
        )
        is False
    )


def test_structural_threshold_scales_with_scene_length() -> None:
    tier, needs_review = _classify_tier(
        nofly=0,
        structural=7,
        verdict=Verdict.NEUTRAL,
        word_count=1441,
    )

    assert tier == "warn"
    assert needs_review is False

    short_tier, short_needs_review = _classify_tier(
        nofly=0,
        structural=7,
        verdict=Verdict.NEUTRAL,
        word_count=1000,
    )

    assert short_tier == "fail"
    assert short_needs_review is True


def test_structural_weighted_threshold_aligns_with_ai_tell_eval() -> None:
    tier, needs_review = _classify_tier(
        nofly=0,
        structural=8,
        structural_weighted=8,
        verdict=Verdict.NEUTRAL,
        word_count=1329,
    )

    assert tier == "fail"
    assert needs_review is True

    borderline_tier, borderline_needs_review = _classify_tier(
        nofly=0,
        structural=6,
        structural_weighted=6,
        verdict=Verdict.NEUTRAL,
        word_count=1329,
    )

    assert borderline_tier == "warn"
    assert borderline_needs_review is False


def test_quality_agent_uses_deterministic_text_metrics(tmp_path: Path) -> None:
    ctx = _make_context(tmp_path)
    agent = QualityAgent(ctx=ctx)
    text = (
        'Mira felt the salt wind cut through the open window. "We can fix it," '
        "Theo said, reaching for the blue plans. She remembered the old inn, "
        "turned toward the harbor light, and set her hand on the warm wood."
    )
    job = JobContext(
        job_id="job1",
        series_id="series1",
        book_id="book1",
        chapter_id=1,
        scene_id="scene1",
        spec=_make_spec(),
        word_count_target=30,
        output_data={
            "editor_agent": {
                "edited_text": text,
                "nofly_violations": 1,
                "structural_flags": 2,
                "structural_weighted_score": 3,
            }
        },
    )

    result = agent.run(job)
    quality = result.output_data["quality_agent"]
    agent.update_ledgers(result)
    totals = ctx.ledger_manager.book_metrics.compute_running_totals()

    assert quality["metrics"]["word_count"] == _compute_text_metrics(text)["word_count"]
    assert quality["metrics"]["dialogue_ratio"] > 0
    assert quality["metrics"]["sensory_density_per_1k"] > 0
    assert quality["metrics"]["ai_tell_count"] == 3.0
    assert quality["structural_weighted_score"] == 3
    assert totals.ai_tell_count_total == 3
    assert totals.dialogue_ratio_running > 0
    assert totals.sensory_density_running > 0
    ctx.ledger_manager.close()


def test_editor_rejects_structural_edit_that_shrinks_below_minimum(tmp_path: Path) -> None:
    ctx = _make_context(tmp_path)

    class FakeRouter:
        def call(self, **_: object) -> SimpleNamespace:
            return SimpleNamespace(edited_text=" ".join(f"short{i}" for i in range(80)))

    agent = EditorAgent(ctx=ctx, model_router=FakeRouter())  # type: ignore[arg-type]
    original = " ".join(f"word{i}" for i in range(100))
    job = JobContext(
        job_id="job1",
        series_id="series1",
        book_id="book1",
        chapter_id=1,
        scene_id="scene1",
        spec=_make_spec(),
        word_count_target=100,
    )

    edited = agent._surgical_edit(
        original,
        "STRUCTURAL ISSUES TO ADDRESS (1 total):\n  [MEDIUM] burstiness",
        job,
    )

    assert edited == original
    ctx.ledger_manager.close()


def test_editor_allows_nofly_edit_to_shrink_below_minimum(tmp_path: Path) -> None:
    ctx = _make_context(tmp_path)

    class FakeRouter:
        def call(self, **_: object) -> SimpleNamespace:
            return SimpleNamespace(edited_text=" ".join(f"short{i}" for i in range(80)))

    agent = EditorAgent(ctx=ctx, model_router=FakeRouter())  # type: ignore[arg-type]
    original = " ".join(f"word{i}" for i in range(100))
    job = JobContext(
        job_id="job1",
        series_id="series1",
        book_id="book1",
        chapter_id=1,
        scene_id="scene1",
        spec=_make_spec(),
        word_count_target=100,
    )

    edited = agent._surgical_edit(
        original,
        'SPECIFIC VIOLATIONS TO FIX:\n  - "a testament to"',
        job,
    )

    assert len(edited.split()) == 80
    ctx.ledger_manager.close()
