"""Nightly EvoSkill pass — run manually for V1; schedule via cron for production.

Usage:
    python scripts/evoskill_nightly.py [--data-root DATA_ROOT]

For V1 this script is executed manually.  In production, schedule it with:
    0 3 * * * python /path/to/scripts/evoskill_nightly.py
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("evoskill_nightly")


def _active_series(data_root: Path) -> list[str]:
    """Return series IDs that have a ``traces/`` subdirectory."""
    if not data_root.is_dir():
        return []
    return [d.name for d in sorted(data_root.iterdir()) if d.is_dir() and (d / "traces").is_dir()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Nightly EvoSkill pass.")
    parser.add_argument(
        "--data-root",
        default="data",
        help="Root data directory (default: data)",
    )
    args = parser.parse_args()
    data_root = Path(args.data_root)

    # Lazy imports so the script fails loudly if the package isn't installed.
    from pipeline.evoskill.evoskill_client import EvoSkillClient
    from pipeline.evoskill.skill_promoter import SkillPromoter
    from pipeline.evoskill.trace_collector import TraceCollector

    collector = TraceCollector(data_root=data_root)
    client = EvoSkillClient()
    promoter = SkillPromoter()

    since = datetime.now(UTC) - timedelta(hours=24)
    series_list = _active_series(data_root)

    if not series_list:
        logger.info("No active series found under %s — nothing to do.", data_root)
        return

    promoted = 0
    skipped = 0

    for series_id in series_list:
        failure_traces = collector.get_failure_traces(series_id, since=since)
        logger.info(
            "Series %s: %d failure trace(s) in the last 24 h.",
            series_id,
            len(failure_traces),
        )

        if not failure_traces:
            skipped += 1
            continue

        # 1. Propose
        try:
            candidate = client.propose_skill(failure_traces, series_id)
        except Exception:
            logger.exception("Series %s: propose_skill failed — skipping.", series_id)
            skipped += 1
            continue

        logger.info(
            "Series %s: proposed skill %s (failure_mode=%s).",
            series_id,
            candidate.skill_id,
            candidate.failure_mode,
        )

        # 2. Evaluate against the same failure traces as a benchmark corpus.
        try:
            eval_result = client.evaluate_skill(candidate, failure_traces)
        except Exception:
            logger.exception("Series %s: evaluate_skill failed — skipping.", series_id)
            skipped += 1
            continue

        logger.info(
            "Series %s: eval skill %s score=%.3f baseline=%.3f improvement=%.3f passed=%s.",
            series_id,
            candidate.skill_id,
            eval_result.score,
            eval_result.baseline_score,
            eval_result.improvement,
            eval_result.passed,
        )

        # 3. Update frontier
        try:
            kept = client.update_frontier(candidate, eval_result)
        except Exception:
            logger.exception("Series %s: update_frontier failed — skipping.", series_id)
            skipped += 1
            continue

        if not kept:
            logger.info(
                "Series %s: skill %s not kept by frontier — no promotion.",
                series_id,
                candidate.skill_id,
            )
            skipped += 1
            continue

        # 4. Promote to wiki / local file
        try:
            promoter.promote_to_wiki(candidate, series_id)
        except Exception:
            logger.exception("Series %s: promote_to_wiki failed.", series_id)
            skipped += 1
            continue

        logger.info(
            "Series %s: skill %s promoted successfully.",
            series_id,
            candidate.skill_id,
        )
        promoted += 1

    logger.info(
        "Nightly pass complete — %d promoted, %d skipped (of %d series).",
        promoted,
        skipped,
        len(series_list),
    )


if __name__ == "__main__":
    main()
