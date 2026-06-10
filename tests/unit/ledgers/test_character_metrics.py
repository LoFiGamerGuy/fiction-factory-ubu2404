"""Unit tests for deterministic per-character dialogue metrics."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from pipeline.agents.quality_agent import QualityAgent
from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
from pipeline.core.project_layout import ProjectLayout
from pipeline.ledgers.character_metrics import (
    compute_character_metrics,
    extract_character_utterances,
)
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)


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


def test_extract_character_utterances_from_speaker_lines_and_tags() -> None:
    scene = """Sarah: "I love this plan. Can you trust me?"
Miles: "No. Wait here!"

"Look at me," Sarah said."""

    utterances = extract_character_utterances(scene)

    assert utterances["sarah"] == ["I love this plan. Can you trust me?", "Look at me,"]
    assert utterances["miles"] == ["No. Wait here!"]


def test_compute_character_metrics_has_required_fields() -> None:
    scene = '''Sarah: "I love this plan. Can you trust me?"
Miles: "No. Wait here!"'''

    metrics = compute_character_metrics(scene)

    assert set(metrics) == {"sarah", "miles"}
    assert metrics["sarah"]["mtld"] > 0
    assert metrics["sarah"]["question_rate"] > 0
    assert metrics["sarah"]["second_person_pronoun_rate"] > 0
    assert metrics["miles"]["exclamatory_rate"] > 0
    assert isinstance(metrics["sarah"]["function_word_vector"], dict)


def test_quality_agent_update_ledgers_persists_character_metrics(tmp_path: Path) -> None:
    ctx = _make_context(tmp_path)
    agent = QualityAgent(ctx=ctx)
    job = JobContext(
        job_id="job1",
        series_id="series1",
        book_id="book1",
        chapter_id=1,
        scene_id="scene1",
        spec=_make_spec(),
        output_data={
            "editor_agent": {
                "edited_text": 'Sarah: "I love this plan."\nMiles: "No. Wait here!"',
                "nofly_violations": 0,
            }
        },
    )

    agent.update_ledgers(job)
    rows = ctx.ledger_manager.book_metrics.character_metrics_history("sarah")

    assert len(rows) == 1
    assert rows[0]["scene_id"] == "scene1"
    assert rows[0]["metrics"]["mtld"] > 0
    assert "function_word_vector" in rows[0]["metrics"]
    ctx.ledger_manager.close()
