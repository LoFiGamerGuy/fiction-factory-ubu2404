"""orchestrator.py — top-level CLI for the fiction-factory pipeline.

Commands:
  --validate-spec <path>     Validate a series spec YAML; exit 0 if valid.
  --init-book <series_id> <book_number>
                             Generate scene inventory for a book.
  --job <scene_id>           Run one scene (job_runner.run_scene).
  --resume <thread_id>       Resume a checkpointed scene run.
  --verify-book <book_id>    Run BookStructuralVerifier; print report.
  --book-publish <book_id>   verify-book then assemble output bundle.
  --status                   Print current pipeline status from ledgers.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


# ── Helpers ────────────────────────────────────────────────────────────────────


def _load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load pipeline config from pipeline_config.json if it exists."""
    path = config_path or Path("pipeline_config.json")
    if path.exists():
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return raw
    return {}


def _get_series_root(config: dict[str, Any], series_id: str) -> Path:
    base = Path(str(config.get("series_root", "data/series")))
    return base / series_id


def _get_layout(config: dict[str, Any], series_id: str, book_id: str) -> Any:
    from pipeline.core.project_layout import ProjectLayout

    return ProjectLayout(series_root=_get_series_root(config, series_id), book_id=book_id)


def _resolve_series_id(config: dict[str, Any], series_id: str | None = None) -> str:
    value = series_id or config.get("series_id")
    if not value:
        raise ValueError("series_id required; pass --series-id or set series_id in config")
    return str(value)


def _resolve_book_id(config: dict[str, Any], book_id: str | None = None) -> str:
    value = book_id or config.get("book_id")
    if not value:
        raise ValueError("book_id required; pass --book-id or set book_id in config")
    return str(value)


def _schema_path(config: dict[str, Any]) -> Path | None:
    raw = config.get("schema_path")
    return Path(str(raw)) if raw else None


def _wiki_page_ref(spec_ref: str) -> str | None:
    for prefix in ("wiki:", "wuphf:"):
        if spec_ref.startswith(prefix):
            page = spec_ref.removeprefix(prefix)
            if not page:
                raise ValueError(f"empty WUPHF wiki page reference: {spec_ref!r}")
            return page
    return None


def _approval_timeout_s(config: dict[str, Any]) -> int:
    return int(config.get("approval_timeout_s", 3600))


def _check_control_budget(config: dict[str, Any], agent_role: str = "orchestrator") -> bool:
    from pipeline.control.paperclip_client import PaperclipClient

    if PaperclipClient().check_budget(agent_role):
        return True
    print(f"ERROR: Paperclip budget exhausted for agent_role={agent_role}", file=sys.stderr)
    return False


def _request_control_approval(
    gate_name: str,
    context: dict[str, Any],
    config: dict[str, Any],
) -> bool:
    from pipeline.control.paperclip_client import PaperclipClient

    if PaperclipClient().request_approval(
        gate_name=gate_name,
        context=context,
        timeout_s=_approval_timeout_s(config),
    ):
        return True
    print(f"ERROR: Paperclip approval gate rejected or timed out: {gate_name}", file=sys.stderr)
    return False


def _record_control_cost(
    config: dict[str, Any],
    agent_role: str = "orchestrator",
    cost_key: str = "orchestrator_cost_usd",
    token_key: str = "orchestrator_tokens_used",
) -> None:
    from pipeline.control.paperclip_client import PaperclipClient

    PaperclipClient().record_cost(
        agent_role=agent_role,
        cost_usd=float(config.get(cost_key, 0.0)),
        tokens_used=int(config.get(token_key, 0)),
    )


def _post_control_activity(
    message: str,
    metadata: dict[str, Any] | None = None,
    room: str | None = None,
) -> None:
    from pipeline.control.wuphf_client import WUPHFClient

    WUPHFClient().post_to_channel(
        "pipeline",
        message,
        room=room,
        metadata=metadata,
    )


def _update_control_wiki(page: str, content: str) -> None:
    from pipeline.control.wuphf_client import WUPHFClient

    WUPHFClient().update_wiki(page, content, author="orchestrator")


def _verify_roma_plan(
    *,
    series_id: str,
    book_id: str,
    series_spec: dict[str, Any],
    book_spec: dict[str, Any],
) -> Any | None:
    from pipeline.control.roma_client import ROMAClient

    roma_spec = {**series_spec, "books": [{**book_spec, "book_id": book_id}]}
    client = ROMAClient()
    plan = client.decompose(roma_spec)
    verification = client.verify(plan)
    if not verification.valid:
        errors = "; ".join(verification.errors) if verification.errors else "unknown error"
        print(
            f"ERROR: ROMA rejected decomposition for {series_id}/{book_id}: {errors}",
            file=sys.stderr,
        )
        return None
    return plan


def _roma_plan_markdown(plan: Any, series_id: str, book_id: str) -> str:
    total_scenes = sum(int(book.total_scenes) for book in plan.book_plans)
    return (
        "# ROMA Planning Summary\n\n"
        f"Series: {series_id}\n"
        f"Book: {book_id}\n"
        f"Book plans: {len(plan.book_plans)}\n"
        f"Total scenes: {total_scenes}\n"
    )


def _load_inventory(layout: Any) -> Any:
    from pipeline.book_structure_planner import SceneInventory

    inventory_path = layout.scene_inventory_path()
    if not inventory_path.exists():
        raise FileNotFoundError(f"scene_inventory.json not found at {inventory_path}")
    return SceneInventory.from_path(inventory_path)


def _find_scene_slot(inventory: Any, scene_id: str) -> Any:
    for slot in inventory.scenes:
        if slot.scene_id == scene_id:
            return slot
    raise ValueError(f"scene_id {scene_id!r} not found in scene inventory")


def _make_project_spec(book_id: str, series_id: str, genre_spec: dict[str, Any]) -> Any:
    from pipeline.profiles.project_spec import (
        ProjectSpec,
        ResolvedAudienceExpectations,
        ResolvedGenreConfig,
        ResolvedGoalWeights,
        ResolvedSensitivityThresholds,
        ResolvedVoiceAxes,
    )

    word_count_target = int(genre_spec.get("word_count_target", 100000))
    scene_functions = tuple(genre_spec.get("scene_function_vocabulary", ()))
    return ProjectSpec(
        book_id=book_id,
        series_id=series_id,
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(
            genre_name=str(genre_spec.get("genre_name", "romance")),
            scene_function_vocabulary=scene_functions,
            word_count_min=1,
            word_count_max=max(word_count_target, 1),
        ),
        sensitivity_thresholds=ResolvedSensitivityThresholds(),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )


def _make_job_context(
    *,
    config: dict[str, Any],
    series_id: str,
    book_id: str,
    scene_id: str,
    slot: Any,
    genre_spec: dict[str, Any],
) -> Any:
    from pipeline.core.job_context import JobContext

    scene_brief = str(
        config.get("scene_brief")
        or getattr(slot, "scene_brief", "")
        or f"Write {slot.scene_function} for {scene_id} in chapter {slot.chapter}."
    )
    return JobContext(
        job_id=str(config.get("job_id") or f"{book_id}:{scene_id}"),
        series_id=series_id,
        book_id=book_id,
        chapter_id=int(slot.chapter),
        scene_id=scene_id,
        spec=_make_project_spec(book_id, series_id, genre_spec),
        model_tier=str(config.get("model_tier", "test")),
        seed=int(config.get("seed", 0)),
        scene_brief=scene_brief,
        word_count_target=int(slot.word_count_target),
        heat_level=int(slot.heat_level_target),
    )


def _make_job_runner(
    *,
    config: dict[str, Any],
    layout: Any,
    series_id: str,
    book_id: str,
    checkpoint_db_path: Path | None = None,
) -> Any:
    from pipeline.core.agent_context import AgentContext
    from pipeline.core.model_router import ModelRouter
    from pipeline.job_runner import JobRunner
    from pipeline.ledgers.ledger_manager import LedgerManager
    from pipeline.profiles.spec_loader import SpecLoader

    model_router_path = Path(str(config.get("model_router_path", "model_router.json")))
    data_root = Path(str(config.get("data_root", layout.series_root / "data" / "ledgers")))
    model_tier = str(config.get("model_tier", "test"))
    router = ModelRouter(config_path=model_router_path, cost_log_path=layout.cost_log_path())
    agent_ctx = AgentContext(
        project_layout=layout,
        spec_loader=SpecLoader(workspace_root=Path(str(config.get("workspace_root", ".")))),
        ledger_manager=LedgerManager(book_id=book_id, series_id=series_id, data_root=data_root),
        log_path=layout.agent_log_path("orchestrator"),
        output_dir=Path(str(config.get("output_dir", "output"))) / book_id,
        model_tier=model_tier,
        llm_provider=str(config.get("llm_provider", "openai")),
    )
    return JobRunner(
        agent_ctx=agent_ctx,
        model_router=router,
        max_revisions=int(config.get("max_revisions", 3)),
        checkpoint_db_path=str(checkpoint_db_path) if checkpoint_db_path else None,
    )


def _read_scene_history(layout: Any) -> list[dict[str, Any]]:
    scene_history_path = layout.scene_history_path()
    if not scene_history_path.exists():
        return []
    scenes_completed: list[dict[str, Any]] = []
    for line in scene_history_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            scenes_completed.append(json.loads(line))
    return scenes_completed


def _record_scene_result(layout: Any, slot: Any, result: Any) -> None:
    final_text = str(result.final_text or "")
    if final_text:
        manuscript_path = layout.manuscript_path()
        manuscript_path.parent.mkdir(parents=True, exist_ok=True)
        existing = manuscript_path.read_text(encoding="utf-8") if manuscript_path.exists() else ""
        separator = "\n\n" if existing else ""
        manuscript_path.write_text(
            f"{existing}{separator}## {slot.scene_id}\n\n{final_text}\n",
            encoding="utf-8",
        )

    history_path = layout.scene_history_path()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_entry = {
        "scene_id": slot.scene_id,
        "thread_id": getattr(result, "thread_id", ""),
        "chapter": slot.chapter,
        "act": slot.act,
        "heat_level": slot.heat_level_target,
        "scene_function": slot.scene_function,
        "required_slot_id": slot.required_slot_id,
        "word_count": len(final_text.split()),
        "convergence_decision": result.convergence_decision,
        "force_resolved": result.force_resolved,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(history_entry) + "\n")


# ── Commands ───────────────────────────────────────────────────────────────────


def cmd_validate_spec(spec_path: str, config: dict[str, Any]) -> int:
    from pipeline.spec_validator_agent import SpecValidatorAgent

    agent = SpecValidatorAgent(schema_path=_schema_path(config))
    wiki_page = _wiki_page_ref(spec_path)
    if wiki_page is not None:
        from pipeline.control.wuphf_client import WUPHFClient

        content = WUPHFClient().read_wiki(wiki_page)
        if not content:
            print(f"ERROR: WUPHF wiki page not found or empty: {wiki_page}", file=sys.stderr)
            return 1
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            encoding="utf-8",
            delete=False,
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            result = agent.validate(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)
    else:
        result = agent.validate(Path(spec_path))
    if result.valid:
        print(f"OK: {spec_path} is valid")
        return 0
    for err in result.errors:
        print(f"ERROR: {err}", file=sys.stderr)
    return 1


def cmd_init_book(series_id: str, book_number: int, config: dict[str, Any]) -> int:
    from pipeline.book_structure_planner import BookStructurePlanner
    from pipeline.spec_loader import SeriesSpecLoader

    book_id = f"book{book_number:02d}"
    layout = _get_layout(config, series_id, book_id)

    loader = SeriesSpecLoader(workspace_root=Path("."), schema_path=_schema_path(config))
    series_spec_path = layout.series_spec_path()
    book_spec_path = layout.book_spec_path()

    if not series_spec_path.exists():
        print(f"ERROR: series spec not found: {series_spec_path}", file=sys.stderr)
        return 1

    try:
        series_spec = loader.load(series_spec_path)
        book_spec = loader.load(book_spec_path) if book_spec_path.exists() else {}
    except Exception as exc:
        print(f"ERROR loading spec: {exc}", file=sys.stderr)
        return 1

    if not _check_control_budget(config):
        return 1
    if not _request_control_approval(
        "spec_signoff",
        {
            "series_id": series_id,
            "book_id": book_id,
            "book_number": book_number,
            "series_spec_path": str(series_spec_path),
            "book_spec_path": str(book_spec_path),
        },
        config,
    ):
        return 1

    roma_plan = _verify_roma_plan(
        series_id=series_id,
        book_id=book_id,
        series_spec=series_spec,
        book_spec=book_spec,
    )
    if roma_plan is None:
        return 1

    planner = BookStructurePlanner()
    inventory = planner.plan(
        book_id=book_id,
        series_id=series_id,
        series_spec=series_spec,
        book_spec=book_spec,
        book_dir=layout.book_dir(),
        inventory_path=layout.scene_inventory_path(),
    )
    _record_control_cost(config, cost_key="init_book_cost_usd", token_key="init_book_tokens_used")
    _post_control_activity(
        (
            f"Initialized book {book_id} for series {series_id}: "
            f"{inventory.total_scenes} scenes planned."
        ),
        metadata={"series_id": series_id, "book_id": book_id, "command": "init-book"},
        room=book_id,
    )
    _update_control_wiki(
        f"planning/{series_id}/{book_id}",
        _roma_plan_markdown(roma_plan, series_id, book_id),
    )
    print(f"Initialized book '{book_id}': {inventory.total_scenes} scenes planned.")
    print(f"Scene inventory: {layout.scene_inventory_path()}")
    return 0


def cmd_job(scene_id: str, series_id: str, book_id: str, config: dict[str, Any]) -> int:
    from pipeline.spec_loader import SeriesSpecLoader

    agent_role = str(config.get("job_agent_role", "orchestrator"))
    if not _check_control_budget(config, agent_role=agent_role):
        return 1

    layout = _get_layout(config, series_id, book_id)
    loader = SeriesSpecLoader(workspace_root=Path("."), schema_path=_schema_path(config))
    try:
        series_spec = loader.load(layout.series_spec_path())
        inventory = _load_inventory(layout)
        slot = _find_scene_slot(inventory, scene_id)
        job_context = _make_job_context(
            config=config,
            series_id=series_id,
            book_id=book_id,
            scene_id=scene_id,
            slot=slot,
            genre_spec=series_spec.get("genre_config", {}),
        )
        checkpoint_db_path = Path(
            str(config.get("checkpoint_db_path", layout.checkpoint_db_path()))
        )
        runner = _make_job_runner(
            config=config,
            layout=layout,
            series_id=series_id,
            book_id=book_id,
            checkpoint_db_path=checkpoint_db_path,
        )
        result = runner.run_scene(job_context)
    except Exception as exc:
        print(f"ERROR running scene job: {exc}", file=sys.stderr)
        return 1

    if result.error and not result.final_text:
        print(f"ERROR: scene '{scene_id}' failed: {result.error}", file=sys.stderr)
        return 1

    _record_scene_result(layout, slot, result)
    _record_control_cost(
        config, agent_role=agent_role, cost_key="job_cost_usd", token_key="job_tokens_used"
    )
    _post_control_activity(
        f"Scene {scene_id} finished with decision={result.convergence_decision}.",
        metadata={
            "series_id": series_id,
            "book_id": book_id,
            "scene_id": scene_id,
            "decision": result.convergence_decision,
            "force_resolved": result.force_resolved,
        },
        room=book_id,
    )
    print(
        f"FINAL: scene '{scene_id}' decision={result.convergence_decision} "
        f"force_resolved={result.force_resolved} thread_id={result.thread_id}"
    )
    return 0


def cmd_resume(
    thread_id: str,
    scene_id: str,
    series_id: str,
    book_id: str,
    config: dict[str, Any],
) -> int:
    from pipeline.spec_loader import SeriesSpecLoader

    layout = _get_layout(config, series_id, book_id)
    checkpoint_db_path = Path(str(config.get("checkpoint_db_path", layout.checkpoint_db_path())))
    loader = SeriesSpecLoader(workspace_root=Path("."), schema_path=_schema_path(config))
    try:
        series_spec = loader.load(layout.series_spec_path())
        inventory = _load_inventory(layout)
        slot = _find_scene_slot(inventory, scene_id)
        job_context = _make_job_context(
            config=config,
            series_id=series_id,
            book_id=book_id,
            scene_id=scene_id,
            slot=slot,
            genre_spec=series_spec.get("genre_config", {}),
        )
        runner = _make_job_runner(
            config=config,
            layout=layout,
            series_id=series_id,
            book_id=book_id,
            checkpoint_db_path=checkpoint_db_path,
        )
        result = runner.resume(thread_id, job_context)
    except Exception as exc:
        print(f"ERROR resuming scene job: {exc}", file=sys.stderr)
        return 1

    if result is None:
        print(
            f"ERROR: checkpoint thread not found or checkpointing disabled: {thread_id}",
            file=sys.stderr,
        )
        return 1
    _record_scene_result(layout, slot, result)
    print(f"RESUMED: scene '{scene_id}' decision={result.convergence_decision}")
    return 0


def cmd_verify_book(book_id: str, series_id: str, config: dict[str, Any]) -> int:
    from pipeline.book_structural_verifier import BookOutput, BookStructuralVerifier
    from pipeline.spec_loader import SeriesSpecLoader

    layout = _get_layout(config, series_id, book_id)
    loader = SeriesSpecLoader(workspace_root=Path("."), schema_path=_schema_path(config))
    genre_name = "romance"
    genre_spec: dict[str, Any] = {}
    try:
        inventory = _load_inventory(layout)
        if layout.series_spec_path().exists():
            series_spec = loader.load(layout.series_spec_path())
            genre_spec = series_spec.get("genre_config", {})
            genre_name = str(genre_spec.get("genre_name", genre_name))
    except Exception as exc:
        print(f"ERROR loading verification inputs: {exc}", file=sys.stderr)
        return 1

    spec = _make_project_spec(book_id, series_id, {**genre_spec, "genre_name": genre_name})

    scenes_completed = _read_scene_history(layout)
    word_count = sum(int(scene.get("word_count", 0)) for scene in scenes_completed)
    manuscript_path = layout.manuscript_path()
    if word_count == 0 and manuscript_path.exists():
        word_count = len(manuscript_path.read_text(encoding="utf-8").split())

    book_output = BookOutput(
        book_id=book_id,
        actual_word_count=word_count,
        scenes_completed=scenes_completed,
    )

    verifier = BookStructuralVerifier()
    report = verifier.verify(
        book_output=book_output, spec=spec, inventory=inventory, genre_spec=genre_spec
    )

    if report.passed:
        print(f"PASSED: book '{book_id}' passed all structural checks.")
    else:
        print(f"FAILED: book '{book_id}' failed {len(report.failed_checks)} check(s):")
        for fc in report.failed_checks:
            print(f"  [{fc.check_name}] {fc.description}")
    return 0 if report.passed else 1


def cmd_book_publish(book_id: str, series_id: str, config: dict[str, Any]) -> int:
    """Verify then assemble output bundle: manuscript.md + generation_report.json."""
    if not _check_control_budget(config):
        return 1

    rc = cmd_verify_book(book_id=book_id, series_id=series_id, config=config)
    if rc != 0:
        print("ERROR: --book-publish aborted; fix verify-book failures first.", file=sys.stderr)
        return rc

    if not _request_control_approval(
        "manuscript_signoff",
        {"series_id": series_id, "book_id": book_id},
        config,
    ):
        return 1

    layout = _get_layout(config, series_id, book_id)
    out_dir = Path(str(config.get("output_dir", "output"))) / book_id
    out_dir.mkdir(parents=True, exist_ok=True)

    manuscript = layout.manuscript_path()
    if manuscript.exists():
        import shutil

        shutil.copy2(manuscript, out_dir / "manuscript.md")
        print(f"Published manuscript → {out_dir / 'manuscript.md'}")

    # Write generation report stub
    report_path = out_dir / "generation_report.json"
    report_path.write_text(
        json.dumps({"book_id": book_id, "series_id": series_id, "status": "published"}, indent=2),
        encoding="utf-8",
    )
    _record_control_cost(config, cost_key="publish_cost_usd", token_key="publish_tokens_used")
    _post_control_activity(
        f"Published book {book_id} for series {series_id}.",
        metadata={"series_id": series_id, "book_id": book_id, "command": "book-publish"},
        room=book_id,
    )
    print(f"Published generation report → {report_path}")
    return 0


def cmd_status(config: dict[str, Any]) -> int:
    series_id = config.get("series_id")
    book_id = config.get("book_id")
    if not series_id or not book_id:
        print("Status: no active run. Configure series_id/book_id, then use --job <scene_id>.")
        return 0

    layout = _get_layout(config, str(series_id), str(book_id))
    inventory_exists = layout.scene_inventory_path().exists()
    scenes_completed = _read_scene_history(layout)
    print(
        f"Status: series={series_id} book={book_id} "
        f"inventory={'yes' if inventory_exists else 'no'} completed_scenes={len(scenes_completed)}"
    )
    return 0


# ── CLI entry ──────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orchestrator",
        description="Fiction-factory pipeline CLI",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate-spec", metavar="SPEC_PATH")
    group.add_argument("--init-book", nargs=2, metavar=("SERIES_ID", "BOOK_NUMBER"))
    group.add_argument("--job", metavar="SCENE_ID")
    group.add_argument("--resume", metavar="THREAD_ID")
    group.add_argument("--verify-book", nargs="+", metavar="BOOK_ID")
    group.add_argument("--book-publish", nargs="+", metavar="BOOK_ID")
    group.add_argument("--status", action="store_true")
    parser.add_argument("--config", metavar="CONFIG_PATH", default=None)
    parser.add_argument("--series-id", default=None)
    parser.add_argument("--book-id", default=None)
    parser.add_argument("--scene-id", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = _load_config(Path(args.config) if args.config else None)
    if args.series_id:
        config = {**config, "series_id": args.series_id}
    if args.book_id:
        config = {**config, "book_id": args.book_id}

    try:
        if args.validate_spec:
            return cmd_validate_spec(args.validate_spec, config)
        if args.init_book:
            series_id, book_number_str = args.init_book
            return cmd_init_book(series_id, int(book_number_str), config)
        if args.job:
            return cmd_job(
                args.job,
                _resolve_series_id(config, args.series_id),
                _resolve_book_id(config, args.book_id),
                config,
            )
        if args.resume:
            scene_id = str(
                args.scene_id or config.get("resume_scene_id") or config.get("scene_id") or ""
            )
            if not scene_id:
                raise ValueError(
                    "scene_id required for --resume; pass --scene-id or set scene_id in config"
                )
            return cmd_resume(
                args.resume,
                scene_id,
                _resolve_series_id(config, args.series_id),
                _resolve_book_id(config, args.book_id),
                config,
            )
        if args.verify_book:
            if len(args.verify_book) not in (1, 2):
                raise ValueError("--verify-book expects BOOK_ID or BOOK_ID SERIES_ID")
            book_id = str(args.verify_book[0])
            series_id = (
                str(args.verify_book[1])
                if len(args.verify_book) == 2
                else _resolve_series_id(config, args.series_id)
            )
            return cmd_verify_book(book_id, series_id, config)
        if args.book_publish:
            if len(args.book_publish) not in (1, 2):
                raise ValueError("--book-publish expects BOOK_ID or BOOK_ID SERIES_ID")
            book_id = str(args.book_publish[0])
            series_id = (
                str(args.book_publish[1])
                if len(args.book_publish) == 2
                else _resolve_series_id(config, args.series_id)
            )
            return cmd_book_publish(book_id, series_id, config)
        if args.status:
            return cmd_status(config)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
