#!/usr/bin/env python3
"""Phase 14 three-scene acceptance runner.

Runs three Romance Module fixture scenes through the full JobRunner path:
WriterAgent -> EditorAgent -> ContinuityAgent -> QualityAgent -> Convergence -> Final.

Default mode is test-tier OpenAI, matching local development. Production-tier
comparison can use the same command with ``--model-tier production`` without
editing ``model_router.json``; this script writes a temporary router config for
the run.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# ruff: noqa: E402
from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
from pipeline.core.managed_agent_config import ManagedAgentConfig
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
from scripts import run_eval

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AcceptanceScene:
    scene_id: str
    chapter_id: int
    scene_brief: str
    word_target: int
    heat_level: int


@dataclass(frozen=True)
class SceneAcceptanceResult:
    scene_id: str
    chapter_id: int
    output_path: str
    convergence_decision: str
    revise_count: int
    force_resolved: bool
    word_count: int
    elapsed_seconds: float
    error: str

    @property
    def passed(self) -> bool:
        return self.error == "" and self.convergence_decision == "GO" and self.word_count > 0


@dataclass(frozen=True)
class AcceptanceSummary:
    run_id: str
    model_tier: str
    provider: str
    dreaming_enabled: bool
    output_dir: str
    scene_dir: str
    scene_count: int
    successful_scenes: int
    go_scenes: int
    elapsed_seconds: float
    eval_passed: bool | None
    eval_scene_count: int | None
    dashboard_summary: dict[str, Any]
    scenes: list[SceneAcceptanceResult]

    @property
    def passed(self) -> bool:
        eval_ok = True if self.eval_passed is None else self.eval_passed
        return (
            self.scene_count == len(self.scenes)
            and self.successful_scenes == self.scene_count
            and self.go_scenes == self.scene_count
            and eval_ok
        )


DEFAULT_SCENES: tuple[AcceptanceScene, ...] = (
    AcceptanceScene(
        scene_id="scene_01_meet_cute",
        chapter_id=1,
        scene_brief=(
            "Emma Chen, an architect trying to save a waterfront renovation project, "
            "meets Marcus Rivera, a chef protecting his family's cafe, when she spills "
            "coffee across his permit drawings. The encounter is awkward, specific, and "
            "charged with reluctant attraction."
        ),
        word_target=550,
        heat_level=1,
    ),
    AcceptanceScene(
        scene_id="scene_02_first_date",
        chapter_id=1,
        scene_brief=(
            "Marcus invites Emma to a quiet staff dinner after closing. Their shared "
            "obsession with craft turns playful, then intimate, as they compare kitchens "
            "and blueprints. End with Emma admitting one concrete fear about the project."
        ),
        word_target=550,
        heat_level=2,
    ),
    AcceptanceScene(
        scene_id="scene_03_first_conflict",
        chapter_id=2,
        scene_brief=(
            "Emma's ex-fiance arrives at the cafe with a funding offer that would gut "
            "Marcus's neighborhood plan. Marcus feels used; Emma feels cornered. The "
            "scene must end unresolved, with both characters wanting repair but choosing distance."
        ),
        word_target=550,
        heat_level=2,
    ),
)


def create_acceptance_spec() -> ProjectSpec:
    """Create a compact Romance Module project spec for the acceptance run."""
    return ProjectSpec(
        book_id="phase14-acceptance-book-01",
        series_id="phase14-acceptance-series",
        voice_axes=ResolvedVoiceAxes(
            internal_monologue_share=0.25,
            dialogue_to_narration_ratio=0.35,
        ),
        genre_config=ResolvedGenreConfig(
            genre_name="romance",
            word_count_min=2000,
            word_count_max=8000,
        ),
        sensitivity_thresholds=ResolvedSensitivityThresholds(max_heat_level=4.0),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )


def write_router_config_for_tier(base_config_path: Path, output_dir: Path, model_tier: str) -> Path:
    """Write a run-local ModelRouter config with the requested active tier."""
    payload = json.loads(base_config_path.read_text(encoding="utf-8"))
    if model_tier not in payload.get("tiers", {}):
        raise ValueError(f"Unknown model tier: {model_tier}")
    payload["model_tier"] = model_tier
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = output_dir / "model_router.run.json"
    config_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return config_path


def run_acceptance(
    *,
    model_tier: str,
    provider: str,
    output_root: Path,
    run_id: str,
    dreaming_enabled: bool,
    run_corpus_eval: bool,
    voice_threshold: float,
    ai_tell_threshold: float,
    max_revisions: int,
) -> AcceptanceSummary:
    """Run the three-scene Phase 14 acceptance path."""
    started = time.monotonic()
    output_dir = output_root / run_id
    data_root = output_dir / "data"
    series_root = output_dir / "series" / "phase14-acceptance-series"
    book_id = "phase14-acceptance-book-01"
    series_id = "phase14-acceptance-series"

    output_dir.mkdir(parents=True, exist_ok=True)
    series_root.mkdir(parents=True, exist_ok=True)

    spec = create_acceptance_spec()
    layout = ProjectLayout(series_root=series_root, book_id=book_id)
    ledger_manager = LedgerManager(book_id=book_id, series_id=series_id, data_root=data_root)
    router_config_path = write_router_config_for_tier(
        WORKSPACE_ROOT / "model_router.json",
        output_dir,
        model_tier,
    )
    router = ModelRouter(
        config_path=router_config_path,
        cost_log_path=output_dir / "cost_log.jsonl",
    )
    managed_config = ManagedAgentConfig(
        managed_agent_mode=dreaming_enabled,
        dreaming_enabled=dreaming_enabled,
        persistent_memory_path=output_dir / "agent_memory",
    )
    agent_ctx = AgentContext(
        project_layout=layout,
        spec_loader=SpecLoader(workspace_root=WORKSPACE_ROOT),
        ledger_manager=ledger_manager,
        log_path=output_dir / "agent.log",
        output_dir=output_dir / "output",
        model_tier=model_tier,
        llm_provider=provider,
        managed_agent_config=managed_config,
    )
    runner = JobRunner(
        agent_ctx=agent_ctx,
        model_router=router,
        max_revisions=max_revisions,
        checkpoint_db_path=str(layout.checkpoint_db_path()),
    )

    scene_results: list[SceneAcceptanceResult] = []
    for index, scene in enumerate(DEFAULT_SCENES, start=1):
        scene_start = time.monotonic()
        job_context = JobContext(
            job_id=f"{run_id}_{scene.scene_id}",
            series_id=series_id,
            book_id=book_id,
            chapter_id=scene.chapter_id,
            scene_id=scene.scene_id,
            spec=spec,
            model_tier=model_tier,
            seed=4200 + index,
            scene_brief=scene.scene_brief,
            word_count_target=scene.word_target,
            heat_level=scene.heat_level,
        )

        logger.info("Running scene %d/%d: %s", index, len(DEFAULT_SCENES), scene.scene_id)
        result = runner.run_scene(job_context)
        output_path = layout.scene_output_path(scene.chapter_id, scene.scene_id)
        word_count = len(result.final_text.split()) if result.final_text else 0
        scene_results.append(
            SceneAcceptanceResult(
                scene_id=scene.scene_id,
                chapter_id=scene.chapter_id,
                output_path=str(output_path),
                convergence_decision=result.convergence_decision,
                revise_count=result.revise_count,
                force_resolved=result.force_resolved,
                word_count=word_count,
                elapsed_seconds=round(time.monotonic() - scene_start, 3),
                error=result.error,
            )
        )

    scene_dir = layout.book_dir() / "scenes"
    eval_passed: bool | None = None
    eval_scene_count: int | None = None
    if run_corpus_eval:
        scene_paths = run_eval._collect_scene_paths(scene_dir)
        suite = run_eval.evaluate_scenes(
            scene_paths=scene_paths,
            voice_threshold=voice_threshold,
            ai_tell_threshold=ai_tell_threshold,
            model_tier=model_tier,
            use_llm_voice=False,
            use_llm_ai_tell=False,
        )
        eval_passed = suite.passed and suite.scene_count >= len(DEFAULT_SCENES)
        eval_scene_count = suite.scene_count

    dashboard = ledger_manager.get_dashboard_summary(book_id, DEFAULT_SCENES[-1].scene_id)
    summary = AcceptanceSummary(
        run_id=run_id,
        model_tier=model_tier,
        provider=provider,
        dreaming_enabled=dreaming_enabled,
        output_dir=str(output_dir),
        scene_dir=str(scene_dir),
        scene_count=len(DEFAULT_SCENES),
        successful_scenes=sum(1 for result in scene_results if result.passed),
        go_scenes=sum(1 for result in scene_results if result.convergence_decision == "GO"),
        elapsed_seconds=round(time.monotonic() - started, 3),
        eval_passed=eval_passed,
        eval_scene_count=eval_scene_count,
        dashboard_summary=dataclasses.asdict(dashboard),
        scenes=scene_results,
    )

    summary_path = output_dir / "phase14_acceptance_summary.json"
    summary_path.write_text(
        json.dumps(_summary_payload(summary), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def _summary_payload(summary: AcceptanceSummary) -> dict[str, Any]:
    payload = dataclasses.asdict(summary)
    payload["passed"] = summary.passed
    return payload


def _default_run_id(model_tier: str, provider: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{model_tier}_{provider}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 14 three-scene acceptance.")
    parser.add_argument("--model-tier", choices=("test", "production"), default="test")
    parser.add_argument(
        "--provider",
        choices=("openai", "anthropic", "ollama"),
        default=os.getenv("FF_LLM_PROVIDER", "openai"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=WORKSPACE_ROOT / "data" / "phase14_acceptance",
    )
    parser.add_argument("--run-id", help="Stable run ID. Defaults to timestamp_tier_provider.")
    parser.add_argument("--with-dreaming", action="store_true", help="Enable managed memory.")
    parser.add_argument(
        "--eval",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run deterministic corpus eval after scene generation.",
    )
    parser.add_argument("--voice-threshold", type=float, default=0.75)
    parser.add_argument("--ai-tell-threshold", type=float, default=0.50)
    parser.add_argument("--max-revisions", type=int, default=1)
    parser.add_argument("--json", action="store_true", help="Print summary JSON only.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.json else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run_id = args.run_id or _default_run_id(args.model_tier, args.provider)
    try:
        summary = run_acceptance(
            model_tier=args.model_tier,
            provider=args.provider,
            output_root=args.output_root,
            run_id=run_id,
            dreaming_enabled=args.with_dreaming,
            run_corpus_eval=args.eval,
            voice_threshold=args.voice_threshold,
            ai_tell_threshold=args.ai_tell_threshold,
            max_revisions=args.max_revisions,
        )
    except Exception as exc:
        logger.error("Phase 14 acceptance failed: %s", exc, exc_info=True)
        return 1

    payload = _summary_payload(summary)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Phase 14 Acceptance")
        print(f"Run: {summary.run_id}")
        print(f"Tier/provider: {summary.model_tier}/{summary.provider}")
        print(f"Scenes: {summary.successful_scenes}/{summary.scene_count} passed")
        print(f"GO decisions: {summary.go_scenes}/{summary.scene_count}")
        if summary.eval_passed is not None:
            eval_status = "PASS" if summary.eval_passed else "FAIL"
            print(f"Eval: {eval_status} ({summary.eval_scene_count} scenes)")
        print(f"Output: {summary.output_dir}")
        print(f"Result: {'PASS' if summary.passed else 'FAIL'}")

    return 0 if summary.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
