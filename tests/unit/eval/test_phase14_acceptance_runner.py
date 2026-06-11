"""Tests for the Phase 14 three-scene acceptance runner."""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

phase14 = importlib.import_module("scripts.run_phase14_acceptance")


def test_write_router_config_for_tier(tmp_path: Path) -> None:
    config_path = tmp_path / "model_router.json"
    config_path.write_text(
        json.dumps(
            {
                "model_tier": "test",
                "tiers": {"test": {}, "production": {}},
                "tier_defaults": {},
            }
        ),
        encoding="utf-8",
    )

    written = phase14.write_router_config_for_tier(config_path, tmp_path / "run", "production")

    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["model_tier"] == "production"
    assert config_path.read_text(encoding="utf-8") != written.read_text(encoding="utf-8")


def test_run_acceptance_with_fake_runner(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    class FakeJobRunner:
        def __init__(self, agent_ctx: Any, **kwargs: object) -> None:
            self.ctx = agent_ctx

        def run_scene(self, job_context: Any) -> Any:
            text = (
                f'"Keep moving," Emma said. "{job_context.scene_id} still matters." '
                "Marcus checked the rain-dark window, then folded the permit map into "
                "a neat square. They were not safe yet, but the next choice was clear."
            )
            output_path = self.ctx.project_layout.scene_output_path(
                job_context.chapter_id,
                job_context.scene_id,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text, encoding="utf-8")

            from pipeline.ledgers.book_metrics_ledger import BookMetricsEvent
            from pipeline.ledgers.ledger_manager import SceneResult

            self.ctx.ledger_manager.update(
                SceneResult(
                    scene_id=job_context.scene_id,
                    book_id=job_context.book_id,
                    chapter_id=str(job_context.chapter_id),
                    timestamp=datetime.now(UTC).isoformat(),
                    scene_type="dialogue",
                    metrics_event=BookMetricsEvent(
                        event_id=job_context.scene_id,
                        book_id=job_context.book_id,
                        scene_id=job_context.scene_id,
                        chapter_id=str(job_context.chapter_id),
                        timestamp=datetime.now(UTC).isoformat(),
                        word_count=len(text.split()),
                        interiority_pct=0.2,
                        dialogue_ratio=0.35,
                        exposition_pct=0.2,
                        action_pct=0.25,
                        sensory_density_per_1k=1.0,
                        em_dash_density=0.0,
                        sentence_length_avg=12.0,
                        ai_tell_count=0,
                        no_fly_violations=0,
                    ),
                )
            )
            return SimpleNamespace(
                final_text=text,
                convergence_decision="GO",
                revise_count=0,
                force_resolved=False,
                error="",
            )

    monkeypatch.setattr(phase14, "JobRunner", FakeJobRunner)

    class FakeEvalSuite:
        passed = True
        scene_count = 3

    monkeypatch.setattr(
        phase14.run_eval,
        "evaluate_scenes",
        lambda **kwargs: FakeEvalSuite(),
    )

    summary = phase14.run_acceptance(
        model_tier="test",
        provider="openai",
        output_root=tmp_path,
        run_id="fixture-run",
        dreaming_enabled=False,
        run_corpus_eval=True,
        voice_threshold=0.75,
        ai_tell_threshold=0.5,
        max_revisions=1,
    )

    assert summary.passed
    assert summary.successful_scenes == 3
    assert summary.go_scenes == 3
    assert summary.eval_passed is True
    assert summary.dashboard_summary["word_count_total"] > 0
    assert len(list(Path(summary.scene_dir).glob("*.md"))) == 3
    assert (tmp_path / "fixture-run" / "phase14_acceptance_summary.json").exists()


def test_main_prints_json_with_fake_acceptance(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    scene_results = [
        phase14.SceneAcceptanceResult(
            scene_id=f"scene_{index}",
            chapter_id=1,
            output_path=str(tmp_path / f"scene_{index}.md"),
            convergence_decision="GO",
            revise_count=0,
            force_resolved=False,
            word_count=35,
            elapsed_seconds=0.1,
            error="",
        )
        for index in range(1, 4)
    ]
    fake_summary = phase14.AcceptanceSummary(
        run_id="cli-run",
        model_tier="test",
        provider="openai",
        dreaming_enabled=False,
        output_dir=str(tmp_path),
        scene_dir=str(tmp_path / "scenes"),
        scene_count=3,
        successful_scenes=3,
        go_scenes=3,
        elapsed_seconds=1.0,
        eval_passed=True,
        eval_scene_count=3,
        dashboard_summary={},
        scenes=scene_results,
    )
    monkeypatch.setattr(phase14, "run_acceptance", lambda **kwargs: fake_summary)

    exit_code = phase14.main(["--json", "--run-id", "cli-run", "--output-root", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["passed"] is True
    assert payload["run_id"] == "cli-run"
