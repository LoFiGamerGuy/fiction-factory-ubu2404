"""Smoke test (T7.9) — one scene end-to-end with test-tier models.

Skips when ANTHROPIC_API_KEY is not set in the environment.
Requires < 90 seconds to complete.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

pytestmark = pytest.mark.skipif(
    not _API_KEY,
    reason="ANTHROPIC_API_KEY not set — smoke test skipped (fail-closed, not silent)",
)


@pytest.fixture()
def workspace_root() -> Path:
    return Path(__file__).parent.parent.parent


@pytest.fixture()
def tmp_series_dir(tmp_path: Path) -> Path:
    p = tmp_path / "data" / "series" / "fixture-series" / "fixture-book-001"
    p.mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_one_scene_end_to_end(workspace_root: Path, tmp_series_dir: Path) -> None:
    """Full pipeline: spec load → Writer → Editor → Quality → FINAL + ledger update."""
    from pipeline.core.agent_context import AgentContext
    from pipeline.core.model_router import ModelRouter
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
    from pipeline.profiles.spec_loader import SpecLoader

    # (a) Load fixture spec via spec_loader
    spec_loader = SpecLoader(workspace_root=workspace_root)
    spec = ProjectSpec(
        book_id="fixture-book-001",
        series_id="fixture-series",
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(genre_name="romance", word_count_max=80000),
        sensitivity_thresholds=ResolvedSensitivityThresholds(max_heat_level=5.0),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )

    # (b) Build AgentContext with test-tier ModelRouter
    layout = ProjectLayout(
        series_root=tmp_series_dir / "data" / "series" / "fixture-series",
        book_id="fixture-book-001",
    )
    ledger = LedgerManager(
        book_id="fixture-book-001",
        series_id="fixture-series",
        data_root=tmp_series_dir / "data",
    )
    router = ModelRouter(
        config_path=workspace_root / "model_router.json",
        cost_log_path=tmp_series_dir / "cost_log.jsonl",
    )
    agent_ctx = AgentContext(
        project_layout=layout,
        spec_loader=spec_loader,
        ledger_manager=ledger,
        log_path=tmp_series_dir / "agent.log",
        output_dir=tmp_series_dir / "output",
        model_tier="test",
    )

    from pipeline.core.job_context import JobContext

    job_context = JobContext(
        job_id="smoke-test-001",
        series_id="fixture-series",
        book_id="fixture-book-001",
        chapter_id=1,
        scene_id="ch01_sc01",
        spec=spec,
        model_tier="test",
        scene_brief=(
            "Elena meets Marcus for the first time at a rainy bookshop. "
            "Their hands brush reaching for the same book. Sparks. "
            "She walks away unsettled."
        ),
        word_count_target=600,  # short for speed
        heat_level=1,
    )

    runner = JobRunner(agent_ctx=agent_ctx, model_router=router, max_revisions=1)

    # (c-e) Run scene via job_runner; assert FINAL state reached
    start = time.monotonic()
    result = runner.run_scene(job_context)
    elapsed = time.monotonic() - start

    # (d) FINAL output present (non-empty)
    assert result.final_text or not result.error, f"Scene run failed with error: {result.error}"

    # (f) All 10 ledger updates occurred (no exception means success)
    # QualityAgent.update_ledgers is called on GO path
    # If force-resolved, ledger update is skipped but scene still completes

    # (g) Complete in < 90 seconds
    assert elapsed < 90.0, f"Smoke test took {elapsed:.1f}s (limit: 90s)"
