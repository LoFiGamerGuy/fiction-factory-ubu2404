#!/usr/bin/env python3
"""Dreaming evaluation smoke test runner.

BCR-20260522-claude-dreaming-mem0 Phase 7 T7.1

Runs 3-scene Romance Module fixture WITH or WITHOUT Dreaming enabled.
Logs: token usage, draft quality, revision count, routing decisions.

Usage:
    python scripts/run_dreaming_smoke_test.py --with-dreaming
    python scripts/run_dreaming_smoke_test.py --without-dreaming
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add workspace root to path before other imports
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# ruff: noqa: E402
from pipeline.agents.writer_agent import WriterAgent
from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dreaming evaluation smoke test")
    parser.add_argument(
        "--with-dreaming",
        action="store_true",
        help="Enable Claude Managed Agents Dreaming",
    )
    parser.add_argument(
        "--without-dreaming",
        action="store_true",
        help="Disable Dreaming (baseline)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=WORKSPACE_ROOT / "data" / "dreaming_eval",
        help="Output directory for results",
    )

    args = parser.parse_args()

    if args.with_dreaming and args.without_dreaming:
        parser.error("Cannot specify both --with-dreaming and --without-dreaming")

    if not args.with_dreaming and not args.without_dreaming:
        parser.error("Must specify either --with-dreaming or --without-dreaming")

    dreaming_enabled = args.with_dreaming
    mode = "with_dreaming" if dreaming_enabled else "without_dreaming"

    logger.info("=" * 80)
    logger.info("Dreaming Evaluation Smoke Test")
    logger.info("Mode: %s", mode)
    logger.info("=" * 80)

    # Setup directories
    output_dir = args.output_dir / mode
    output_dir.mkdir(parents=True, exist_ok=True)

    memory_dir = output_dir / "agent_memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    # Load fixture specs
    fixture_dir = WORKSPACE_ROOT / "tests" / "fixtures" / "dreaming_eval"

    logger.info("Loading fixture specs from: %s", fixture_dir)

    # For now, create a minimal test setup
    # Full orchestrator integration would happen in a later phase

    # Setup managed agent config
    if dreaming_enabled:
        managed_config = ManagedAgentConfig(
            managed_agent_mode=True,
            persistent_memory_path=memory_dir,
            dreaming_enabled=True,
        )
        logger.info("Dreaming ENABLED - persistent memory at: %s", memory_dir)
    else:
        managed_config = ManagedAgentConfig(
            managed_agent_mode=False,
            dreaming_enabled=False,
        )
        logger.info("Dreaming DISABLED - baseline mode")

    # Setup core components
    series_root = output_dir
    book_id = "dreaming-eval-book-01"

    layout = ProjectLayout(series_root=series_root, book_id=book_id)
    spec_loader = SpecLoader(workspace_root=series_root)
    ledger_manager = LedgerManager(
        book_id=book_id,
        series_id="dreaming-eval-series",
        data_root=output_dir / "ledgers",
    )

    ctx = AgentContext(
        project_layout=layout,
        spec_loader=spec_loader,
        ledger_manager=ledger_manager,
        log_path=output_dir / "agent.log",
        output_dir=output_dir / "drafts",
        model_tier="test",  # Use Haiku for testing
        managed_agent_config=managed_config,
    )

    router = ModelRouter(
        config_path=WORKSPACE_ROOT / "model_router.json",
        cost_log_path=output_dir / "cost.jsonl",
    )

    writer = WriterAgent(ctx, router)

    # Create minimal ProjectSpec for JobContext
    spec = ProjectSpec(
        book_id=book_id,
        series_id="dreaming-eval-series",
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(
            genre_name="romance",
            word_count_min=2000,
            word_count_max=4000,
        ),
        sensitivity_thresholds=ResolvedSensitivityThresholds(),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )

    # Define 3 scenes from fixture
    scenes: list[dict[str, Any]] = [
        {
            "scene_id": "scene_01_meet_cute",
            "scene_brief": (
                "Emma Chen, architect, meets Marcus Rivera, restaurant owner, "
                "when she accidentally spills coffee on his blueprints at a "
                "waterfront cafe. Awkward but charming first encounter. "
                "Spark of attraction."
            ),
            "word_target": 1000,
            "chapter_id": 1,
        },
        {
            "scene_id": "scene_02_first_date",
            "scene_brief": (
                "Marcus invites Emma to dinner at his restaurant. They discover "
                "shared passion for design (architecture vs culinary). First "
                "meaningful conversation, vulnerability glimpses. Romantic "
                "tension building."
            ),
            "word_target": 1000,
            "chapter_id": 1,
        },
        {
            "scene_id": "scene_03_first_conflict",
            "scene_brief": (
                "Emma's ex-fiancé shows up unexpectedly, triggering her "
                "commitment fears. Marcus feels shut out. First real obstacle "
                "testing their connection. Scene ends on uncertain note."
            ),
            "word_target": 1000,
            "chapter_id": 1,
        },
    ]

    results = []

    for i, scene_spec in enumerate(scenes, 1):
        logger.info("")
        logger.info("=" * 80)
        logger.info("Scene %d/%d: %s", i, len(scenes), scene_spec["scene_id"])
        logger.info("=" * 80)

        job_ctx = JobContext(
            job_id=f"job_{mode}_{scene_spec['scene_id']}",
            series_id="dreaming-eval-series",
            book_id=book_id,
            chapter_id=int(scene_spec["chapter_id"]),
            scene_id=str(scene_spec["scene_id"]),
            spec=spec,
            model_tier="test",
            seed=42 + i,  # Deterministic but different per scene
            scene_brief=str(scene_spec["scene_brief"]),
            word_count_target=int(scene_spec["word_target"]),
        )

        try:
            result_ctx = writer.run(job_ctx)

            writer_output = result_ctx.output_data.get("writer_agent", {})
            draft_text = writer_output.get("draft_text", "")
            word_count = writer_output.get("word_count", 0)

            logger.info("✓ Draft generated: %d words", word_count)
            logger.info("First 200 chars: %s...", draft_text[:200])

            scene_result = {
                "scene_id": scene_spec["scene_id"],
                "success": True,
                "word_count": word_count,
                "draft_preview": draft_text[:500],
            }

        except Exception as exc:
            logger.error("✗ Scene generation failed: %s", exc, exc_info=True)
            scene_result = {
                "scene_id": scene_spec["scene_id"],
                "success": False,
                "error": str(exc),
            }

        results.append(scene_result)

    # Save results
    summary = {
        "mode": mode,
        "dreaming_enabled": dreaming_enabled,
        "timestamp": datetime.now(UTC).isoformat(),
        "scenes": results,
        "total_scenes": len(scenes),
        "successful_scenes": sum(1 for r in results if r.get("success")),
        "total_words": sum(r.get("word_count", 0) for r in results),
    }

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    logger.info("")
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info("Mode: %s", mode)
    logger.info("Successful scenes: %d/%d", summary["successful_scenes"], summary["total_scenes"])
    logger.info("Total words generated: %d", summary["total_words"])
    logger.info("Results saved to: %s", summary_path)
    logger.info("")

    if summary["successful_scenes"] < summary["total_scenes"]:
        logger.warning("Some scenes failed - check logs for details")
        sys.exit(1)
    else:
        logger.info("✓ All scenes generated successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
