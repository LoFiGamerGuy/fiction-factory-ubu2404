#!/usr/bin/env python3
"""Apply accepted targeted revisions into a revised manuscript variant."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# ruff: noqa: E402
from pipeline.revision.revision_apply import RevisionApplicationError, apply_revision_outputs

DEFAULT_COMPARISON_PATH = Path("/tmp/opencode/targeted_revision_comparison.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply accepted revised scenes into a no-live manuscript variant."
    )
    parser.add_argument(
        "--comparison-path",
        type=Path,
        default=DEFAULT_COMPARISON_PATH,
        help="Path to targeted_revision_comparison.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for accepted revisions and manuscript_revised.md.",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        help="Optional source book_run_summary.json override.",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Apply only passed revised scenes from a failed comparison report.",
    )
    parser.add_argument("--json", action="store_true", help="Print full application JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    comparison_path = args.comparison_path.resolve()
    if not comparison_path.exists():
        raise SystemExit(f"Comparison report not found: {comparison_path}")
    try:
        report = apply_revision_outputs(
            comparison_path,
            args.output_dir.resolve(),
            allow_partial=args.allow_partial,
            summary_path=args.summary_path.resolve() if args.summary_path is not None else None,
        )
    except RevisionApplicationError as exc:
        raise SystemExit(str(exc)) from exc

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Revision Application")
        print(f"Run: {report.get('source_run_id')}")
        print(f"Book: {report.get('series_id')}/{report.get('book_id')}")
        print(f"Status: {report.get('status')}")
        print(f"Applied scenes: {report.get('applied_scene_count')}")
        print(f"Manuscript: {report.get('manuscript_path')}")
        print(f"Summary: {report.get('application_summary_path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
