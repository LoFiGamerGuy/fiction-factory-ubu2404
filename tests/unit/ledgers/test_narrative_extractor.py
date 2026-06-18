"""Deterministic narrative extraction and runtime ledger dispatch tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from pipeline.agents.quality_agent import QualityAgent
from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
from pipeline.core.project_layout import ProjectLayout
from pipeline.ledgers.character_metrics import compute_character_metrics
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.ledgers.narrative_extractor import extract_narrative_events
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


def _make_job(text: str, *, heat_level: int = 3) -> JobContext:
    return JobContext(
        job_id="job1",
        series_id="series1",
        book_id="book1",
        chapter_id=5,
        scene_id="ch05_sc01",
        spec=_make_spec(),
        scene_brief="Second chance renovation setup at the family inn.",
        heat_level=heat_level,
        word_count_target=100,
        output_data={
            "editor_agent": {
                "edited_text": text,
                "nofly_violations": 0,
                "structural_flags": 0,
            }
        },
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


def test_extract_narrative_events_emits_runtime_ledger_events() -> None:
    text = (
        'Sarah: "Can we fix the renovation contract?"\n'
        'Miles: "I discovered the truth about the old budget secret."\n'
        "Sarah touched Miles's hand, kissed him, and agreed the family inn project "
        "could be repaired."
    )
    metrics = {
        "word_count": 38.0,
        "dialogue_ratio": 0.5,
        "interiority_pct": 0.1,
        "action_pct": 0.2,
    }
    extraction = extract_narrative_events(
        job_context=_make_job(text),
        text=text,
        metrics=metrics,
        character_metrics=compute_character_metrics(text),
        timestamp=datetime.now(UTC).isoformat(),
    )

    assert extraction.scene_type == "dialogue"
    assert {event.character_id for event in extraction.character_arc_events} == {
        "miles",
        "sarah",
    }
    assert extraction.intimacy_events[0].pair_id == "miles__sarah"
    assert extraction.revelation_events[0].known_by_characters == ["miles", "sarah"]
    assert {event.subplot_type for event in extraction.subplot_events} == {
        "family",
        "professional",
        "romantic",
    }
    assert extraction.trope_events[0].trope_id == "second_chance_romance"
    assert {event.event_type for event in extraction.promise_events} == {"opened", "resolved"}


def test_quality_agent_update_ledgers_dispatches_narrative_events(tmp_path: Path) -> None:
    text = (
        'Sarah: "Can we fix the renovation contract?"\n'
        'Miles: "I discovered the truth about the old budget secret."\n'
        "Sarah touched Miles's hand, kissed him, and agreed the family inn project "
        "could be repaired."
    )
    ctx = _make_context(tmp_path)
    agent = QualityAgent(ctx=ctx)
    job = _make_job(text, heat_level=4)

    agent.update_ledgers(job)
    dashboard = ctx.ledger_manager.get_dashboard_summary("book1", "ch05_sc01")

    assert dashboard.scene_rhythm == ["sex"]
    assert dashboard.sex_scene_count == 1
    assert dashboard.character_arcs == {"miles": "wound_open", "sarah": "wound_open"}
    assert dashboard.intimacy_pairs == {"miles__sarah": "first_kiss"}
    assert dashboard.reader_info_known == 1
    assert dashboard.subplots_open == 3
    assert dashboard.trope_beats_pending == 1
    assert dashboard.promises_open == 1
    ctx.ledger_manager.close()
