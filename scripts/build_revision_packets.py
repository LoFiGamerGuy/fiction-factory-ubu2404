#!/usr/bin/env python3
"""Build no-live targeted revision packets from a book autopsy backlog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# ruff: noqa: E402
from pipeline.revision.targeted_packets import build_targeted_revision_packets

DEFAULT_BACKLOG_PATH = Path(
    "data/series/cedar-harbor-romance/data/books/book01/book_revision_backlog.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build no-live targeted revision packets.")
    parser.add_argument(
        "--backlog-path",
        type=Path,
        default=DEFAULT_BACKLOG_PATH,
        help="Path to book_revision_backlog.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for packet JSON/Markdown files.",
    )
    parser.add_argument(
        "--no-current-text",
        action="store_true",
        help="Omit current scene text from packets.",
    )
    parser.add_argument(
        "--max-scene-chars",
        type=int,
        default=12000,
        help="Maximum scene text characters embedded per packet; 0 means no truncation.",
    )
    parser.add_argument("--json", action="store_true", help="Print full manifest JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    backlog_path = args.backlog_path.resolve()
    if not backlog_path.exists():
        raise SystemExit(f"Backlog not found: {backlog_path}")
    if args.max_scene_chars < 0:
        raise SystemExit("--max-scene-chars must be >= 0")

    manifest = build_targeted_revision_packets(
        backlog_path,
        args.output_dir.resolve(),
        include_current_text=not args.no_current_text,
        max_scene_chars=args.max_scene_chars,
    )
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print("Targeted Revision Packets")
        print(f"Run: {manifest.get('source_run_id')}")
        print(f"Book: {manifest.get('series_id')}/{manifest.get('book_id')}")
        print(f"Packets: {manifest.get('packet_count')}")
        print(f"Output: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
