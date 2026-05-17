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
    base = Path(config.get("series_root", "data/series"))
    return base / series_id


# ── Commands ───────────────────────────────────────────────────────────────────


def cmd_validate_spec(spec_path: str, config: dict[str, Any]) -> int:
    from pipeline.spec_validator_agent import SpecValidatorAgent

    agent = SpecValidatorAgent()
    result = agent.validate(Path(spec_path))
    if result.valid:
        print(f"OK: {spec_path} is valid")
        return 0
    else:
        for err in result.errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1


def cmd_init_book(series_id: str, book_number: int, config: dict[str, Any]) -> int:
    from pipeline.book_structure_planner import BookStructurePlanner
    from pipeline.spec_loader import SeriesSpecLoader

    series_root = _get_series_root(config, series_id)
    book_id = f"book{book_number:02d}"

    loader = SeriesSpecLoader(workspace_root=Path("."))
    series_spec_path = series_root / "spec.yaml"
    book_spec_path = series_root / book_id / "spec.yaml"

    if not series_spec_path.exists():
        print(f"ERROR: series spec not found: {series_spec_path}", file=sys.stderr)
        return 1

    try:
        series_spec = loader.load(series_spec_path)
        book_spec = loader.load(book_spec_path) if book_spec_path.exists() else {}
    except Exception as exc:
        print(f"ERROR loading spec: {exc}", file=sys.stderr)
        return 1

    book_dir = series_root / book_id
    planner = BookStructurePlanner()
    inventory = planner.plan(
        book_id=book_id,
        series_id=series_id,
        series_spec=series_spec,
        book_spec=book_spec,
        book_dir=book_dir,
    )
    print(f"Initialized book '{book_id}': {inventory.total_scenes} scenes planned.")
    print(f"Scene inventory: {book_dir / 'scene_inventory.json'}")
    return 0


def cmd_job(scene_id: str, config: dict[str, Any]) -> int:
    print(
        "ERROR: --job requires a configured JobRunner with spec/book context. "
        "Use JobRunner directly or extend this command with --series-id/--book-id flags.",
        file=sys.stderr,
    )
    return 1


def cmd_resume(thread_id: str, config: dict[str, Any]) -> int:
    print(
        f"ERROR: --resume requires a configured SceneStateMachine. "
        f"Use SceneStateMachine.resume('{thread_id}') directly.",
        file=sys.stderr,
    )
    return 1


def cmd_verify_book(book_id: str, series_id: str, config: dict[str, Any]) -> int:
    import json as _json

    from pipeline.book_structural_verifier import BookOutput, BookStructuralVerifier
    from pipeline.book_structure_planner import SceneInventory, SceneSlot
    from pipeline.profiles.project_spec import (
        ProjectSpec,
        ResolvedAudienceExpectations,
        ResolvedGenreConfig,
        ResolvedGoalWeights,
        ResolvedSensitivityThresholds,
        ResolvedVoiceAxes,
    )

    series_root = _get_series_root(config, series_id)
    book_dir = series_root / book_id
    inventory_path = book_dir / "scene_inventory.json"

    if not inventory_path.exists():
        print(f"ERROR: scene_inventory.json not found at {inventory_path}", file=sys.stderr)
        return 1

    raw_inv = _json.loads(inventory_path.read_text(encoding="utf-8"))
    slots = [SceneSlot(**s) for s in raw_inv["scenes"]]
    inventory = SceneInventory(
        book_id=raw_inv["book_id"],
        series_id=raw_inv["series_id"],
        total_scenes=raw_inv["total_scenes"],
        word_count_target=raw_inv["word_count_target"],
        scenes=slots,
    )

    # Build a minimal spec from the series spec if available
    from pipeline.spec_loader import SeriesSpecLoader

    loader = SeriesSpecLoader(workspace_root=Path("."))
    series_spec_path = series_root / "spec.yaml"
    genre_name = "romance"
    genre_spec: dict[str, Any] = {}
    if series_spec_path.exists():
        try:
            ss = loader.load(series_spec_path)
            genre_name = ss.get("genre_config", {}).get("genre_name", "romance")
            genre_spec = ss.get("genre_config", {})
        except Exception:
            pass

    spec = ProjectSpec(
        book_id=book_id,
        series_id=series_id,
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(genre_name=genre_name),
        sensitivity_thresholds=ResolvedSensitivityThresholds(),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )

    # Build BookOutput from scene history if available
    manuscript_path = book_dir / "manuscript.md"
    word_count = 0
    if manuscript_path.exists():
        word_count = len(manuscript_path.read_text(encoding="utf-8").split())
    scene_history_path = book_dir / "scene_history.jsonl"
    scenes_completed: list[dict[str, Any]] = []
    if scene_history_path.exists():
        for line in scene_history_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                scenes_completed.append(_json.loads(line))

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
    rc = cmd_verify_book(book_id=book_id, series_id=series_id, config=config)
    if rc != 0:
        print("ERROR: --book-publish aborted; fix verify-book failures first.", file=sys.stderr)
        return rc

    series_root = _get_series_root(config, series_id)
    book_dir = series_root / book_id
    out_dir = Path(config.get("output_dir", "output")) / book_id
    out_dir.mkdir(parents=True, exist_ok=True)

    manuscript = book_dir / "manuscript.md"
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
    print(f"Published generation report → {report_path}")
    return 0


def cmd_status(config: dict[str, Any]) -> int:
    print("Status: no active run. Use --job <scene_id> to start.")
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
    group.add_argument("--verify-book", nargs=2, metavar=("BOOK_ID", "SERIES_ID"))
    group.add_argument("--book-publish", nargs=2, metavar=("BOOK_ID", "SERIES_ID"))
    group.add_argument("--status", action="store_true")
    parser.add_argument("--config", metavar="CONFIG_PATH", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = _load_config(Path(args.config) if args.config else None)

    if args.validate_spec:
        return cmd_validate_spec(args.validate_spec, config)
    if args.init_book:
        series_id, book_number_str = args.init_book
        return cmd_init_book(series_id, int(book_number_str), config)
    if args.job:
        return cmd_job(args.job, config)
    if args.resume:
        return cmd_resume(args.resume, config)
    if args.verify_book:
        book_id, series_id = args.verify_book
        return cmd_verify_book(book_id, series_id, config)
    if args.book_publish:
        book_id, series_id = args.book_publish
        return cmd_book_publish(book_id, series_id, config)
    if args.status:
        return cmd_status(config)
    return 1


if __name__ == "__main__":
    sys.exit(main())
