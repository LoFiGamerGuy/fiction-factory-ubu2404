"""No-live targeted revision packet generation tests."""

from __future__ import annotations

import json
from hashlib import sha1
from pathlib import Path

from pipeline.revision.targeted_packets import build_targeted_revision_packets


def test_build_targeted_revision_packets_writes_json_markdown_and_manifest(
    tmp_path: Path,
) -> None:
    scene_path = tmp_path / "ch01_sc01.md"
    scene_path.write_text("Sarah stood by the harbor. We need to choose.\n", encoding="utf-8")
    backlog_path = _write_backlog(tmp_path, scene_path)
    output_dir = tmp_path / "packets"

    manifest = build_targeted_revision_packets(backlog_path, output_dir)

    assert manifest["schema_version"] == "targeted_revision_packet_manifest.v1"
    assert manifest["source_run_id"] == "run1"
    assert manifest["packet_count"] == 1
    packet_row = manifest["packets"][0]
    packet_path = Path(packet_row["json_path"])
    markdown_path = Path(packet_row["markdown_path"])
    assert packet_path.exists()
    assert markdown_path.exists()

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    issue_ids = {issue["issue_id"] for issue in packet["issues"]}
    assert issue_ids == {"ISS-word-budget-1", "ISS-repeated-phrase-1"}
    assert [issue["issue_id"] for issue in packet["book_level_context"]] == ["ISS-character-arc-1"]
    assert packet["current_text_included"] is True
    assert "Sarah stood by the harbor" in packet["current_text"]
    assert packet["current_scene_sha1"]
    assert any("word target" in objective for objective in packet["revision_objectives"])
    assert any("We need to" in objective for objective in packet["revision_objectives"])
    assert any("content-policy" in item for item in packet["constraints"])
    assert packet["output_contract"]["status"] == "packet_only_no_live"

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Revision Packet: ch01_sc01" in markdown
    assert "ISS-word-budget-1" in markdown
    assert "## Current Text" in markdown


def test_build_targeted_revision_packets_can_omit_current_text(tmp_path: Path) -> None:
    scene_path = tmp_path / "ch01_sc01.md"
    scene_path.write_text("A" * 50, encoding="utf-8")
    backlog_path = _write_backlog(tmp_path, scene_path)
    output_dir = tmp_path / "packets"

    manifest = build_targeted_revision_packets(
        backlog_path,
        output_dir,
        include_current_text=False,
        max_scene_chars=10,
    )

    packet = json.loads(Path(manifest["packets"][0]["json_path"]).read_text(encoding="utf-8"))
    markdown = Path(manifest["packets"][0]["markdown_path"]).read_text(encoding="utf-8")
    assert packet["current_text_included"] is False
    assert packet["current_text"] == ""
    assert packet["current_scene_sha1"] == sha1(("A" * 50).encode("utf-8")).hexdigest()
    assert "Current text omitted" in markdown


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
                        "issue_id": "ISS-word-budget-1",
                        "scope": "scene",
                        "scene_id": "ch01_sc01",
                        "chapter_id": "1",
                        "category": "word_budget",
                        "severity": 3,
                        "signal": "scene_over_target",
                        "evidence": "Scene is long.",
                        "recommendation": "Compress exposition.",
                        "source": "book_pacing_reviewer",
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
                    {
                        "issue_id": "ISS-character-arc-1",
                        "scope": "book",
                        "scene_id": None,
                        "chapter_id": None,
                        "category": "character_arc",
                        "severity": 5,
                        "signal": "no_character_arc_events",
                        "evidence": "No arc events.",
                        "recommendation": "Track character arc movement.",
                        "source": "character_arc_reviewer",
                        "metadata": {},
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
                            "severity_total": 3,
                            "issue_ids": ["ISS-word-budget-1"],
                            "current_scene_path": str(scene_path),
                            "current_word_count": 1400,
                            "adjusted_word_count_target": 1000,
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    return backlog_path
