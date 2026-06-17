#!/usr/bin/env python3
"""Unattended production full-book runner.

This is the production counterpart to ``scripts/run_book_acceptance.py``. It
uses a committed series scaffold, runs scenes in ``scene_inventory.json`` order,
and keeps model-tier changes in a run-local router config so ``model_router.json``
remains defaulted to ``test``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# ruff: noqa: E402
from pipeline.book_runner import BookRunner, SceneJobRunner, scenes_from_inventory
from pipeline.book_structural_verifier import BookOutput, BookStructuralVerifier
from pipeline.book_structure_planner import BookStructurePlanner, SceneInventory
from pipeline.core.agent_context import AgentContext
from pipeline.core.managed_agent_config import ManagedAgentConfig
from pipeline.core.model_router import ModelRouter
from pipeline.core.project_layout import ProjectLayout
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
from pipeline.spec_loader import SeriesSpecLoader
from pipeline.spec_validator_agent import SpecValidatorAgent
from scripts import run_eval

logger = logging.getLogger(__name__)

JobRunnerFactory = Callable[[AgentContext], SceneJobRunner]


def load_config(config_path: Path) -> dict[str, Any]:
    """Load a production runner JSON config."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Config must be a JSON object: {config_path}")
    return raw


def resolve_path(raw_path: str | Path, *, base: Path = WORKSPACE_ROOT) -> Path:
    """Resolve config paths relative to the configured workspace root."""
    path = Path(raw_path)
    return path if path.is_absolute() else base / path


def resolve_series_id(config: Mapping[str, Any], series_id: str | None) -> str:
    value = series_id or config.get("series_id")
    if not value:
        raise ValueError("series_id required; pass --series-id or set series_id in config")
    return str(value)


def resolve_book_id(config: Mapping[str, Any], book_id: str | None) -> str:
    value = book_id or config.get("book_id")
    if not value:
        raise ValueError("book_id required; pass --book-id or set book_id in config")
    return str(value)


def schema_path_from_config(config: Mapping[str, Any], *, workspace_root: Path) -> Path | None:
    raw = config.get("schema_path")
    return resolve_path(str(raw), base=workspace_root) if raw else None


def validate_series_spec(series_spec_path: Path, schema_path: Path | None = None) -> None:
    """Validate the series spec before any scene generation starts."""
    result = SpecValidatorAgent(schema_path=schema_path).validate(series_spec_path)
    if result.valid:
        return
    joined = "; ".join(result.errors) if result.errors else "unknown validation error"
    raise ValueError(f"Series spec failed validation: {joined}")


def load_or_generate_inventory(
    *,
    layout: ProjectLayout,
    series_id: str,
    book_id: str,
    series_spec: Mapping[str, Any],
    book_spec: Mapping[str, Any],
) -> tuple[SceneInventory, bool]:
    """Load scene_inventory.json, or generate it from specs when missing."""
    inventory_path = layout.scene_inventory_path()
    if inventory_path.exists():
        return SceneInventory.from_path(inventory_path), False

    inventory = BookStructurePlanner().plan(
        book_id=book_id,
        series_id=series_id,
        series_spec=dict(series_spec),
        book_spec=dict(book_spec),
        book_dir=layout.book_dir(),
        inventory_path=inventory_path,
    )
    return inventory, True


def limit_inventory(inventory: SceneInventory, max_scenes: int | None) -> SceneInventory:
    """Return an in-memory partial inventory for spend-capped proof runs."""
    if max_scenes is None:
        return inventory
    if max_scenes <= 0:
        raise ValueError("--max-scenes must be positive")
    scenes = list(inventory.scenes[:max_scenes])
    return SceneInventory(
        book_id=inventory.book_id,
        series_id=inventory.series_id,
        total_scenes=len(scenes),
        word_count_target=inventory.word_count_target,
        scenes=scenes,
    )


def write_router_config_for_tier(base_config_path: Path, output_dir: Path, model_tier: str) -> Path:
    """Write a run-local ModelRouter config with the requested active tier."""
    payload: dict[str, Any] = json.loads(base_config_path.read_text(encoding="utf-8"))
    if model_tier not in payload.get("tiers", {}):
        raise ValueError(f"Unknown model tier: {model_tier}")
    payload["model_tier"] = model_tier
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = output_dir / "model_router.run.json"
    config_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return config_path


def run_ledger_data_root(run_dir: Path) -> Path:
    """Return the run-local ledger root for production full-book execution."""
    return run_dir / "ledgers"


def make_project_spec(
    *,
    book_id: str,
    series_id: str,
    series_spec: Mapping[str, Any],
    book_spec: Mapping[str, Any],
) -> ProjectSpec:
    """Build the compact runtime ProjectSpec used by JobRunner agents."""
    genre_spec = _mapping(series_spec.get("genre_config"))
    sensitivity_overrides = _mapping(series_spec.get("sensitivity_overrides"))
    hard_thresholds = _mapping(sensitivity_overrides.get("hard_thresholds"))
    word_count_target = int(
        book_spec.get("word_count_target") or genre_spec.get("word_count_target") or 100000
    )
    chapter_count = int(book_spec.get("chapter_count") or genre_spec.get("chapter_count") or 30)
    scene_functions = tuple(str(item) for item in genre_spec.get("scene_function_vocabulary", ()))
    reader_contract = tuple(str(item) for item in genre_spec.get("reader_contract", ()))

    return ProjectSpec(
        book_id=book_id,
        series_id=series_id,
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(
            genre_name=str(genre_spec.get("genre_name", "romance")),
            genre_module_status=str(genre_spec.get("genre_module_status", "scaffold")),
            scene_function_vocabulary=scene_functions,
            word_count_min=max(1, int(word_count_target * 0.7)),
            word_count_max=max(1, int(word_count_target * 1.3)),
            chapter_count_min=max(1, chapter_count),
            chapter_count_max=max(1, chapter_count),
            reader_contract=reader_contract,
        ),
        sensitivity_thresholds=ResolvedSensitivityThresholds(
            max_heat_level=float(hard_thresholds.get("max_heat_level", 5.0)),
            max_violence_intensity=float(hard_thresholds.get("max_violence_intensity", 5.0)),
        ),
        goal_weights=ResolvedGoalWeights(
            intent=str(series_spec.get("goal_profile", "kdp_commercial"))
        ),
        audience_expectations=ResolvedAudienceExpectations(
            reader_lens=str(series_spec.get("audience_profile", "romance_reader")),
            expectation_set=reader_contract,
        ),
    )


def build_eval_status(
    *,
    scene_paths: list[Path],
    model_tier: str,
    required_scene_count: int,
    voice_threshold: float,
    ai_tell_threshold: float,
) -> dict[str, Any]:
    """Run deterministic corpus eval for the generated scene set."""
    suite = run_eval.evaluate_scenes(
        scene_paths=scene_paths,
        voice_threshold=voice_threshold,
        ai_tell_threshold=ai_tell_threshold,
        model_tier=model_tier,
        use_llm_voice=False,
        use_llm_ai_tell=False,
    )
    return {
        "passed": suite.passed and suite.scene_count >= required_scene_count,
        "scene_count": suite.scene_count,
        "required_scene_count": required_scene_count,
        "scenes": [
            {
                "scene_path": str(run.scene_path),
                "passed": run.passed,
                "voice_consistency": run.voice.score,
                "ai_tell": run.ai_tell.score,
            }
            for run in suite.runs
        ],
    }


def build_verifier_status(
    *,
    result: Any,
    spec: ProjectSpec,
    inventory: SceneInventory,
    run_inventory: SceneInventory,
    genre_spec: Mapping[str, Any],
) -> dict[str, Any]:
    """Run strict structural verification, skipping intentional partial proofs."""
    if len(run_inventory.scenes) < len(inventory.scenes):
        return {
            "passed": None,
            "skipped": True,
            "reason": "partial_run",
            "required_scene_count": len(inventory.scenes),
            "attempted_scene_count": len(run_inventory.scenes),
        }

    slot_by_id = {slot.scene_id: slot for slot in inventory.scenes}
    scenes_completed: list[dict[str, Any]] = []
    for status in result.scenes:
        if not status.successful:
            continue
        slot = slot_by_id[status.scene_id]
        scenes_completed.append(
            {
                "scene_id": status.scene_id,
                "chapter": status.chapter_id,
                "act": slot.act,
                "heat_level": slot.heat_level_target,
                "scene_function": slot.scene_function,
                "required_slot_id": slot.required_slot_id,
                "word_count": status.word_count,
            }
        )

    report = BookStructuralVerifier().verify(
        book_output=BookOutput(
            book_id=spec.book_id,
            actual_word_count=sum(status.word_count for status in result.scenes),
            scenes_completed=scenes_completed,
        ),
        spec=spec,
        inventory=inventory,
        genre_spec=dict(genre_spec),
    )
    return {
        "passed": report.passed,
        "skipped": False,
        "failed_checks": [
            {"check_name": check.check_name, "description": check.description}
            for check in report.failed_checks
        ],
    }


def build_dashboard_check_status(*, layout: ProjectLayout, book_id: str) -> dict[str, Any]:
    """Verify the local dashboard API can resolve the generated book summary."""
    try:
        from fastapi.testclient import TestClient  # noqa: PLC0415

        from api.main import app  # noqa: PLC0415
    except Exception as exc:
        return {"passed": False, "error": str(exc)}

    had_data_root = hasattr(app.state, "data_root")
    old_data_root = getattr(app.state, "data_root", None)
    app.state.data_root = layout.series_root
    try:
        with TestClient(app) as client:
            summary_response = client.get(f"/books/{book_id}/summary")
            quality_response = client.get(f"/books/{book_id}/quality_gates")
        summary_payload = summary_response.json() if summary_response.status_code == 200 else {}
        quality_payload = quality_response.json() if quality_response.status_code == 200 else []
        return {
            "passed": summary_response.status_code == 200
            and bool(summary_payload.get("summary_found")),
            "summary_status_code": summary_response.status_code,
            "summary_found": bool(summary_payload.get("summary_found")),
            "quality_gates_status_code": quality_response.status_code,
            "quality_gate_count": len(quality_payload) if isinstance(quality_payload, list) else 0,
        }
    finally:
        if had_data_root:
            app.state.data_root = old_data_root
        elif hasattr(app.state, "data_root"):
            delattr(app.state, "data_root")


def run_passed(
    *,
    generation_passed: bool,
    force_resolved_scenes: int,
    eval_status: Mapping[str, Any] | None,
    verifier_status: Mapping[str, Any] | None,
    dashboard_api_status: Mapping[str, Any] | None,
) -> bool:
    """Return the top-level unattended-run decision."""
    return (
        generation_passed
        and force_resolved_scenes == 0
        and _optional_status_passed(eval_status)
        and _optional_status_passed(verifier_status)
        and _optional_status_passed(dashboard_api_status)
    )


def run_full_book(
    *,
    config_path: Path,
    series_id: str | None = None,
    book_id: str | None = None,
    run_id: str | None = None,
    model_tier: str | None = None,
    provider: str | None = None,
    max_scenes: int | None = None,
    resume: bool = True,
    force: bool = False,
    stop_on_error: bool = True,
    run_corpus_eval: bool = True,
    run_dashboard_checks: bool = True,
    voice_threshold: float = 0.75,
    ai_tell_threshold: float = 0.50,
    job_runner_factory: JobRunnerFactory | None = None,
) -> dict[str, Any]:
    """Run a production book inventory unattended and return summary payload."""
    config = load_config(config_path)
    workspace_root = resolve_path(str(config.get("workspace_root", ".")), base=WORKSPACE_ROOT)
    resolved_series_id = resolve_series_id(config, series_id)
    resolved_book_id = resolve_book_id(config, book_id)
    series_root = (
        resolve_path(
            str(config.get("series_root", "data/series")),
            base=workspace_root,
        )
        / resolved_series_id
    )
    layout = ProjectLayout(series_root=series_root, book_id=resolved_book_id)
    run_id = run_id or _default_run_id(resolved_series_id, resolved_book_id)
    run_dir = layout.book_dir() / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    validate_series_spec(
        layout.series_spec_path(),
        schema_path=schema_path_from_config(config, workspace_root=workspace_root),
    )
    series_loader = SeriesSpecLoader(
        workspace_root=workspace_root,
        schema_path=schema_path_from_config(config, workspace_root=workspace_root),
    )
    series_spec = series_loader.load(layout.series_spec_path())
    book_spec = (
        series_loader.load(layout.book_spec_path()) if layout.book_spec_path().exists() else {}
    )
    inventory, inventory_generated = load_or_generate_inventory(
        layout=layout,
        series_id=resolved_series_id,
        book_id=resolved_book_id,
        series_spec=series_spec,
        book_spec=book_spec,
    )
    if inventory.series_id != resolved_series_id or inventory.book_id != resolved_book_id:
        raise ValueError(
            "scene_inventory.json identity mismatch: "
            f"expected {resolved_series_id}/{resolved_book_id}, "
            f"found {inventory.series_id}/{inventory.book_id}"
        )
    run_inventory = limit_inventory(inventory, max_scenes)
    if not run_inventory.scenes:
        raise ValueError("scene_inventory.json has no scenes to run")

    runtime_defaults = _mapping(series_spec.get("runtime_defaults"))
    effective_model_tier = str(
        model_tier or config.get("model_tier") or runtime_defaults.get("model_tier") or "test"
    )
    effective_provider = str(
        provider
        or config.get("llm_provider")
        or runtime_defaults.get("llm_provider")
        or os.getenv("FF_LLM_PROVIDER", "openai")
    )
    seed = int(config.get("seed") or runtime_defaults.get("seed") or 0)
    configured_data_root = resolve_path(
        str(config.get("data_root", layout.series_root / "data" / "ledgers")),
        base=workspace_root,
    )
    ledger_data_root = run_ledger_data_root(run_dir)
    if force and ledger_data_root.exists():
        shutil.rmtree(ledger_data_root)
    ledger_data_root.mkdir(parents=True, exist_ok=True)
    output_dir = resolve_path(str(config.get("output_dir", "output")), base=workspace_root) / run_id
    router_config_path = write_router_config_for_tier(
        resolve_path(
            str(config.get("model_router_path", "model_router.json")), base=workspace_root
        ),
        run_dir,
        effective_model_tier,
    )
    cost_log_path = run_dir / "cost_log.jsonl"
    router = ModelRouter(config_path=router_config_path, cost_log_path=cost_log_path)
    ledger_manager = LedgerManager(
        book_id=resolved_book_id,
        series_id=resolved_series_id,
        data_root=ledger_data_root,
    )
    managed_agent_mode = bool(
        config.get("managed_agent_mode", runtime_defaults.get("managed_agent_mode", False))
    )
    managed_config = ManagedAgentConfig(
        managed_agent_mode=managed_agent_mode,
        dreaming_enabled=managed_agent_mode,
        persistent_memory_path=run_dir / "agent_memory",
    )
    agent_ctx = AgentContext(
        project_layout=layout,
        spec_loader=SpecLoader(workspace_root=workspace_root),
        ledger_manager=ledger_manager,
        log_path=layout.agent_log_path("run_full_book"),
        output_dir=output_dir,
        model_tier=effective_model_tier,
        llm_provider=effective_provider,
        managed_agent_config=managed_config,
    )

    try:
        job_runner = job_runner_factory(agent_ctx) if job_runner_factory is not None else None
        runner = BookRunner(
            agent_ctx=agent_ctx,
            model_router=router,
            job_runner=job_runner,
            max_revisions=int(config.get("max_revisions", 3)),
            checkpoint_db_path=layout.checkpoint_db_path(),
            status_path=run_dir / "book_run_status.jsonl",
        )
        spec = make_project_spec(
            book_id=resolved_book_id,
            series_id=resolved_series_id,
            series_spec=series_spec,
            book_spec=book_spec,
        )
        result = runner.run_inventory(
            run_id=run_id,
            spec=spec,
            inventory=run_inventory,
            base_seed=seed,
            stop_on_error=stop_on_error,
            resume=resume,
            force=force,
            word_budget_target=inventory.word_count_target,
        )
        scenes = scenes_from_inventory(run_inventory)
        manuscript = runner.assemble_manuscript(scenes) if result.passed else None
        eval_scene_paths = [
            layout.scene_output_path(slot.chapter, slot.scene_id) for slot in run_inventory.scenes
        ]
        eval_status = (
            build_eval_status(
                scene_paths=eval_scene_paths,
                model_tier=effective_model_tier,
                required_scene_count=len(run_inventory.scenes),
                voice_threshold=voice_threshold,
                ai_tell_threshold=ai_tell_threshold,
            )
            if result.passed and run_corpus_eval
            else None
        )
        verifier_status = (
            build_verifier_status(
                result=result,
                spec=spec,
                inventory=inventory,
                run_inventory=run_inventory,
                genre_spec=_mapping(series_spec.get("genre_config")),
            )
            if result.passed
            else None
        )
        base_metadata = {
            "run_type": "production_full_book",
            "config_path": str(config_path),
            "run_dir": str(run_dir),
            "output_dir": str(output_dir),
            "inventory_path": str(layout.scene_inventory_path()),
            "inventory_generated": inventory_generated,
            "inventory_total_scene_count": len(inventory.scenes),
            "run_scene_count": len(run_inventory.scenes),
            "max_scenes": max_scenes,
            "partial_run": len(run_inventory.scenes) < len(inventory.scenes),
            "resume_enabled": resume,
            "force_rerun": force,
            "stop_on_error": stop_on_error,
            "eval_enabled": run_corpus_eval,
            "dashboard_checks_enabled": run_dashboard_checks,
            "router_config_path": str(router_config_path),
            "cost_log_path": str(cost_log_path),
            "configured_data_root": str(configured_data_root),
            "ledger_data_root": str(ledger_data_root),
            "managed_agent_mode": managed_agent_mode,
        }
        payload = runner.write_book_run_summary(
            result=result,
            provider=effective_provider,
            manuscript=manuscript,
            eval_status=eval_status,
            verifier_status=verifier_status,
            cost_log_path=cost_log_path,
            extra_metadata={**base_metadata, "run_passed": False},
        )
        dashboard_status = (
            build_dashboard_check_status(layout=layout, book_id=resolved_book_id)
            if run_dashboard_checks
            else None
        )
        passed = run_passed(
            generation_passed=result.passed,
            force_resolved_scenes=result.force_resolved_scenes,
            eval_status=eval_status,
            verifier_status=verifier_status,
            dashboard_api_status=dashboard_status,
        )
        payload = runner.write_book_run_summary(
            result=result,
            provider=effective_provider,
            manuscript=manuscript,
            eval_status=eval_status,
            verifier_status=verifier_status,
            cost_log_path=cost_log_path,
            extra_metadata={
                **base_metadata,
                "dashboard_api_status": dashboard_status,
                "run_passed": passed,
            },
        )
        return payload
    finally:
        ledger_manager.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a production full-book inventory unattended.")
    parser.add_argument("--config", type=Path, required=True, help="Path to pipeline_config.json.")
    parser.add_argument("--series-id", help="Override config series_id.")
    parser.add_argument("--book-id", help="Override config book_id.")
    parser.add_argument("--run-id", help="Stable run ID. Defaults to timestamp_series_book.")
    parser.add_argument("--model-tier", choices=("test", "production"), help="Override model tier.")
    parser.add_argument(
        "--provider",
        choices=("openai", "anthropic", "ollama"),
        help="Override LLM provider.",
    )
    parser.add_argument("--max-scenes", type=int, help="Run only the first N inventory scenes.")
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip completed scenes for this run ID. Enabled by default.",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate all selected scenes.")
    error_group = parser.add_mutually_exclusive_group()
    error_group.add_argument(
        "--stop-on-error",
        dest="stop_on_error",
        action="store_true",
        default=True,
        help="Stop at the first failed scene. Default.",
    )
    error_group.add_argument(
        "--continue-on-error",
        dest="stop_on_error",
        action="store_false",
        help="Attempt later scenes after a scene failure.",
    )
    parser.add_argument(
        "--eval",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run deterministic corpus eval after successful generation. Use --no-eval to skip.",
    )
    parser.add_argument(
        "--dashboard-checks",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run local FastAPI dashboard summary checks. Enabled by default.",
    )
    parser.add_argument("--voice-threshold", type=float, default=0.75)
    parser.add_argument("--ai-tell-threshold", type=float, default=0.50)
    parser.add_argument("--json", action="store_true", help="Print summary JSON only.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_scenes is not None and args.max_scenes <= 0:
        parser.error("--max-scenes must be positive")
    logging.basicConfig(
        level=logging.WARNING if args.json else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        payload = run_full_book(
            config_path=args.config,
            series_id=args.series_id,
            book_id=args.book_id,
            run_id=args.run_id,
            model_tier=args.model_tier,
            provider=args.provider,
            max_scenes=args.max_scenes,
            resume=args.resume,
            force=args.force,
            stop_on_error=args.stop_on_error,
            run_corpus_eval=args.eval,
            run_dashboard_checks=args.dashboard_checks,
            voice_threshold=args.voice_threshold,
            ai_tell_threshold=args.ai_tell_threshold,
        )
    except Exception as exc:
        logger.error("Full-book run failed: %s", exc, exc_info=True)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Full Book Run")
        print(f"Run: {payload['run_id']}")
        print(f"Series/book: {payload['series_id']}/{payload['book_id']}")
        print(f"Tier/provider: {payload['model_tier']}/{payload['provider']}")
        print(
            f"Scenes: {payload['successful_scenes']}/{payload['planned_scene_count']} "
            f"completed (inventory total {payload['inventory_total_scene_count']})"
        )
        print(f"GO decisions: {payload['go_scenes']}/{payload['planned_scene_count']}")
        print(f"Force-resolved: {payload['force_resolved_scenes']}")
        if payload.get("partial_run"):
            print("Verifier: SKIPPED (partial run)")
        else:
            verifier_status = payload.get("verifier_status")
            if isinstance(verifier_status, dict):
                print(f"Verifier: {'PASS' if verifier_status.get('passed') else 'FAIL'}")
        eval_status = payload.get("eval_status")
        if isinstance(eval_status, dict):
            print(
                f"Eval: {'PASS' if eval_status.get('passed') else 'FAIL'} "
                f"({eval_status.get('scene_count', 0)} scenes)"
            )
        dashboard_status = payload.get("dashboard_api_status")
        if isinstance(dashboard_status, dict):
            print(f"Dashboard summary: {'PASS' if dashboard_status.get('passed') else 'FAIL'}")
        print(f"Manuscript: {payload['manuscript_path']}")
        print(f"Summary: {payload['summary_path']}")
        print(f"Run dir: {payload['run_dir']}")
        print(f"Result: {'PASS' if payload['run_passed'] else 'FAIL'}")

    return 0 if payload["run_passed"] else 1


def _default_run_id(series_id: str, book_id: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{series_id}_{book_id}"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _optional_status_passed(status: Mapping[str, Any] | None) -> bool:
    if status is None:
        return True
    if bool(status.get("skipped")):
        return True
    return bool(status.get("passed"))


if __name__ == "__main__":
    raise SystemExit(main())
