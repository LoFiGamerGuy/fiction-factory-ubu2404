"""Unit tests for ContinuityAgent."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.continuity.bible_steward import BibleSteward
from pipeline.continuity.bible_types import BibleDelta
from pipeline.continuity.continuity_agent import ContinuityAgent
from pipeline.continuity.loop_tracker import LoopTracker
from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
from pipeline.core.managed_agent_config import ManagedAgentConfig
from pipeline.core.project_layout import ProjectLayout
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.ledgers.promise_ledger import PromiseLedger
from pipeline.ledgers.series_promise_ledger import SeriesPromiseLedger
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
        genre_config=ResolvedGenreConfig(),
        sensitivity_thresholds=ResolvedSensitivityThresholds(),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )


def _make_context(tmp_path: Path, *, dreaming_enabled: bool = False) -> AgentContext:
    managed_config = ManagedAgentConfig(
        managed_agent_mode=dreaming_enabled,
        persistent_memory_path=tmp_path / "memory" if dreaming_enabled else None,
        dreaming_enabled=dreaming_enabled,
    )
    return AgentContext(
        project_layout=ProjectLayout(series_root=tmp_path / "series", book_id="book1"),
        spec_loader=MagicMock(),
        ledger_manager=LedgerManager(book_id="book1", data_root=tmp_path / "data"),
        log_path=tmp_path / "agent.log",
        output_dir=tmp_path / "output",
        model_tier="test",
        managed_agent_config=managed_config,
    )


def _make_agent(tmp_path: Path, *, dreaming_enabled: bool = False) -> ContinuityAgent:
    steward = BibleSteward(tmp_path / "bible")
    promise = PromiseLedger(book_id="book1", data_root=tmp_path / "data")
    series_promise = SeriesPromiseLedger(series_id="series1", data_root=tmp_path / "data")
    tracker = LoopTracker(promise_ledger=promise, series_promise_ledger=series_promise)
    return ContinuityAgent(
        ctx=_make_context(tmp_path, dreaming_enabled=dreaming_enabled),
        bible_steward=steward,
        loop_tracker=tracker,
    )


def _make_job(**output_data: object) -> JobContext:
    return JobContext(
        job_id="job1",
        series_id="series1",
        book_id="book1",
        chapter_id=5,
        scene_id="ch05_sc01",
        spec=_make_spec(),
        output_data=dict(output_data),
    )


def test_instantiates_and_runs_clean(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    result = agent.run(_make_job())

    assert result.bible_contradiction is False
    assert result.overdue_promises == []
    assert (tmp_path / "agent.log").exists()


def test_flags_bible_contradiction(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    steward = agent._steward
    existing = BibleDelta(
        delta_id="d001",
        entity_id="char_alice",
        entity_type="character",
        operation="upsert",
        new_attributes={"role": "protagonist"},
    )
    steward.commit_delta(steward.propose_delta(existing), book_id="book1")

    result = agent.run(
        _make_job(
            bible_deltas=[
                {
                    "delta_id": "d002",
                    "entity_id": "char_alice",
                    "entity_type": "location",
                    "operation": "upsert",
                    "new_attributes": {"name": "Thornfield"},
                }
            ]
        )
    )

    assert result.bible_contradiction is True


def test_populates_overdue_promises(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    with patch.object(
        agent._tracker._promise,
        "_all_payloads",
        return_value=[
            {
                "promise_id": "p001",
                "must_resolve_by": "3",
                "resolution_state": "open",
                "description": "Must resolve",
            }
        ],
    ):
        result = agent.run(_make_job())

    assert result.overdue_promises == ["p001"]


def test_dreaming_memory_saved_when_enabled(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path, dreaming_enabled=True)
    agent.run(_make_job())

    memory_file = tmp_path / "memory" / "ContinuityAgent.memory.json"
    data = json.loads(memory_file.read_text(encoding="utf-8"))
    assert data["scenes_checked"] == 1
    assert data["total_contradictions"] == 0
    assert data["recent_scenes"][0]["scene_id"] == "ch05_sc01"


def test_dreaming_memory_not_saved_when_disabled(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path, dreaming_enabled=False)
    agent.run(_make_job())

    assert not (tmp_path / "memory" / "ContinuityAgent.memory.json").exists()
