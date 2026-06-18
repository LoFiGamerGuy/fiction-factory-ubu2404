#!/usr/bin/env python3
"""Compare targeted revised scene outputs against revision packets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# ruff: noqa: E402
from pipeline.revision.revision_compare import compare_revision_outputs

DEFAULT_MANIFEST_PATH = Path(
    "data/series/cedar-harbor-romance/data/books/book01/revision_packets/"
    "revision_packet_manifest.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="No-live comparison of revised scenes against targeted revision packets."
    )
    parser.add_argument(
        "--packet-manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to revision_packet_manifest.json.",
    )
    parser.add_argument(
        "--revised-dir",
        type=Path,
        required=True,
        help="Directory containing revised scene markdown/text files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for targeted_revision_comparison.json.",
    )
    parser.add_argument(
        "--nofly-catalog-path",
        type=Path,
        help="Optional ai_tell_catalog JSON path for NoFlyScanner checks.",
    )
    parser.add_argument("--json", action="store_true", help="Print full comparison JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    packet_manifest = args.packet_manifest.resolve()
    revised_dir = args.revised_dir.resolve()
    if not packet_manifest.exists():
        raise SystemExit(f"Packet manifest not found: {packet_manifest}")
    if not revised_dir.exists():
        raise SystemExit(f"Revised directory not found: {revised_dir}")

    report = compare_revision_outputs(
        packet_manifest,
        revised_dir,
        nofly_catalog_path=args.nofly_catalog_path.resolve()
        if args.nofly_catalog_path is not None
        else None,
        output_path=args.output.resolve() if args.output is not None else None,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Targeted Revision Comparison")
        print(f"Run: {report.get('source_run_id')}")
        print(f"Book: {report.get('series_id')}/{report.get('book_id')}")
        print(f"Scenes: {report.get('scene_count')}")
        print(f"Passed: {report.get('passed')}")
        failed = report.get("failed_scene_ids") or []
        if failed:
            print(f"Failed scenes: {', '.join(str(value) for value in failed)}")
        if args.output is not None:
            print(f"Report: {args.output.resolve()}")
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
