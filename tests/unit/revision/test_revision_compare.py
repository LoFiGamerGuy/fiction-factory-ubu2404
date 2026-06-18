"""No-live targeted revision output comparison tests."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.revision.revision_compare import compare_revision_outputs
from pipeline.revision.targeted_packets import build_targeted_revision_packets


def test_compare_revision_outputs_passes_when_revision_improves_packet_issues(
    tmp_path: Path,
) -> None:
    scene_path = tmp_path / "ch01_sc01.md"
    scene_path.write_text(
        "We need to decide. We need to breathe. It is not enough. It is courage. "
        "This inn was a testament to old promises.",
        encoding="utf-8",
    )
    backlog_path = _write_backlog(tmp_path, scene_path)
    packet_manifest = build_targeted_revision_packets(backlog_path, tmp_path / "packets")
    revised_dir = tmp_path / "revised"
    revised_dir.mkdir()
    (revised_dir / "ch01_sc01_revised.md").write_text(
        "Sarah touched the railing and chose repair work with Miles before the council "
        "returned tonight.",
        encoding="utf-8",
    )

    report = compare_revision_outputs(
        Path(packet_manifest["packets"][0]["json_path"]).parent / "revision_packet_manifest.json",
        revised_dir,
        nofly_catalog_path=_write_nofly_catalog(tmp_path),
    )

    assert report["passed"] is True
    scene = report["scene_results"][0]
    assert scene["checks"]["current_hash_matches_packet"] is True
    assert scene["checks"]["repeated_phrases_reduced"] is True
    assert scene["checks"]["no_fly_violations_not_worse"] is True
    assert scene["deltas"]["no_fly_violations"] < 0
    assert scene["deltas"]["structural_weighted_score"] < 0


def test_compare_revision_outputs_fails_on_contract_and_phrase_regression(
    tmp_path: Path,
) -> None:
    scene_path = tmp_path / "ch01_sc01.md"
    scene_path.write_text(
        "We need to decide. We need to breathe. It is not enough. It is courage.",
        encoding="utf-8",
    )
    backlog_path = _write_backlog(tmp_path, scene_path)
    packet_manifest = build_targeted_revision_packets(backlog_path, tmp_path / "packets")
    revised_dir = tmp_path / "revised"
    revised_dir.mkdir()
    (revised_dir / "ch01_sc01_revised.md").write_text(
        "We need to decide. We need to breathe.\n\n---\n\nAlternate version.",
        encoding="utf-8",
    )

    report = compare_revision_outputs(
        Path(packet_manifest["packets"][0]["json_path"]).parent / "revision_packet_manifest.json",
        revised_dir,
        nofly_catalog_path=_write_nofly_catalog(tmp_path),
    )

    assert report["passed"] is False
    assert report["failed_scene_ids"] == ["ch01_sc01"]
    checks = report["scene_results"][0]["checks"]
    assert checks["no_markdown_separator_appendix"] is False
    assert checks["repeated_phrases_reduced"] is False


def _write_backlog(tmp_path: Path, scene_path: Path) -> Path:
    backlog_path = tmp_path / "book_revision_backlog.json"
    backlog_path.write_text(
        json.dumps(
            {
                "schema_version": "revision_backlog.v1",
                "run_id": "run1",
                "book_id": "book1",
                "series_id": "series1",
                "issues": [
                    {
                        "issue_id": "ISS-ai-tell-1",
                        "scope": "scene",
                        "scene_id": "ch01_sc01",
                        "chapter_id": "1",
                        "category": "ai_tell_density",
                        "severity": 4,
                        "signal": "ai_tell_density_high",
                        "evidence": "Weighted structural density is high.",
                        "recommendation": "Replace abstractions with concrete action.",
                        "source": "ai_tell_reviewer",
                        "metadata": {},
                    },
                    {
                        "issue_id": "ISS-repeated-phrase-1",
                        "scope": "book",
                        "scene_id": None,
                        "chapter_id": None,
                        "category": "repeated_phrase",
                        "severity": 4,
                        "signal": "repeated_phrase_across_book",
                        "evidence": "Phrase appears often.",
                        "recommendation": "Vary repeated phrasing.",
                        "source": "commercial_readability_reviewer",
                        "metadata": {"phrase": "We need to", "scene_ids": ["ch01_sc01"]},
                    },
                ],
                "targeted_revision_plan": {
                    "schema_version": "targeted_revision_plan.v1",
                    "source_run_id": "run1",
                    "target_scene_count": 1,
                    "selection_strategy": "highest_sum_issue_severity",
                    "status": "planned_no_live",
                    "scenes": [
                        {
                            "scene_id": "ch01_sc01",
                            "chapter_id": "1",
                            "severity_total": 8,
                            "issue_ids": ["ISS-ai-tell-1"],
                            "current_scene_path": str(scene_path),
                            "current_word_count": 20,
                            "adjusted_word_count_target": 15,
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    return backlog_path


def _write_nofly_catalog(tmp_path: Path) -> Path:
    catalog_path = tmp_path / "ai_tell_catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "patterns": [
                    {
                        "pattern_id": "testament_to",
                        "category": "ai_tell",
                        "severity": 5,
                        "detection_method": "rule",
                        "regex_or_rule": "a testament to",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return catalog_path
