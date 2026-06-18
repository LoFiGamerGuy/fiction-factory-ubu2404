#!/usr/bin/env python3
"""Analyze a completed book run and write a revision backlog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# ruff: noqa: E402
from pipeline.revision.book_autopsy import build_book_revision_backlog

DEFAULT_SUMMARY_PATH = Path(
    "data/series/cedar-harbor-romance/data/books/book01/book_run_summary.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze a generated book run offline.")
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=DEFAULT_SUMMARY_PATH,
        help="Path to book_run_summary.json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path for book_revision_backlog.json. Defaults next to the summary.",
    )
    parser.add_argument(
        "--targeted-plan-output",
        type=Path,
        help="Optional separate targeted_revision_plan.json path.",
    )
    parser.add_argument("--target-scenes", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="Print full backlog JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.target_scenes <= 0:
        raise SystemExit("--target-scenes must be positive")
    summary_path = args.summary_path.resolve()
    if not summary_path.exists():
        raise SystemExit(f"Summary not found: {summary_path}")

    backlog = build_book_revision_backlog(
        summary_path,
        target_scene_count=args.target_scenes,
    )
    output_path = args.output or summary_path.with_name("book_revision_backlog.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(backlog, indent=2, sort_keys=True), encoding="utf-8")

    if args.targeted_plan_output is not None:
        plan = backlog["targeted_revision_plan"]
        args.targeted_plan_output.parent.mkdir(parents=True, exist_ok=True)
        args.targeted_plan_output.write_text(
            json.dumps(plan, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    if args.json:
        print(json.dumps(backlog, indent=2, sort_keys=True))
    else:
        _print_summary(backlog, output_path)
    return 0


def _print_summary(backlog: dict[str, Any], output_path: Path) -> None:
    plan = backlog.get("targeted_revision_plan", {})
    print("Book Run Autopsy")
    print(f"Run: {backlog.get('run_id')}")
    print(f"Book: {backlog.get('series_id')}/{backlog.get('book_id')}")
    print(f"Issues: {backlog.get('issue_count')}")
    print(f"Targeted scenes: {plan.get('target_scene_count', 0)}")
    print(f"Backlog: {output_path}")


if __name__ == "__main__":
    raise SystemExit(main())
