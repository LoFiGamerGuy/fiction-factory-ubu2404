"""No-live revision application tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.revision.revision_apply import RevisionApplicationError, apply_revision_outputs


def test_apply_revision_outputs_refuses_failed_comparison_without_partial(
    tmp_path: Path,
) -> None:
    paths = _write_revision_fixture(
        tmp_path,
        comparison_passed=False,
        result_passed_by_scene={"ch01_sc01": False},
    )

    with pytest.raises(RevisionApplicationError, match="refusing to apply"):
        apply_revision_outputs(paths["comparison"], tmp_path / "applied")


def test_apply_revision_outputs_assembles_revised_manuscript_when_comparison_passed(
    tmp_path: Path,
) -> None:
    paths = _write_revision_fixture(
        tmp_path,
        comparison_passed=True,
        result_passed_by_scene={"ch01_sc01": True},
    )

    report = apply_revision_outputs(paths["comparison"], tmp_path / "applied")

    manuscript = Path(report["manuscript_path"]).read_text(encoding="utf-8")
    assert report["status"] == "applied_no_live"
    assert report["applied_scene_ids"] == ["ch01_sc01"]
    assert "Revised first scene text." in manuscript
    assert "Original second scene text." in manuscript
    assert "Original first scene text." not in manuscript
    assert (tmp_path / "applied" / "accepted_revisions" / "ch01_sc01.md").exists()
    assert paths["scene_one"].read_text(encoding="utf-8") == "Original first scene text."
    summary = json.loads(
        (tmp_path / "applied" / "revision_application_summary.json").read_text(encoding="utf-8")
    )
    assert summary["manuscript_path"] == report["manuscript_path"]
    assert [scene["source"] for scene in summary["scenes"]] == ["revised", "original"]


def test_apply_revision_outputs_allows_partial_and_skips_failed_revisions(
    tmp_path: Path,
) -> None:
    paths = _write_revision_fixture(
        tmp_path,
        comparison_passed=False,
        result_passed_by_scene={"ch01_sc01": True, "ch01_sc02": False},
    )

    report = apply_revision_outputs(
        paths["comparison"],
        tmp_path / "applied",
        allow_partial=True,
    )

    manuscript = Path(report["manuscript_path"]).read_text(encoding="utf-8")
    assert report["status"] == "partial_applied_no_live"
    assert report["applied_scene_ids"] == ["ch01_sc01"]
    assert report["skipped_failed_scene_ids"] == ["ch01_sc02"]
    assert "Revised first scene text." in manuscript
    assert "Original second scene text." in manuscript
    assert "Revised second scene text." not in manuscript


def _write_revision_fixture(
    tmp_path: Path,
    *,
    comparison_passed: bool,
    result_passed_by_scene: dict[str, bool],
) -> dict[str, Path]:
    scene_dir = tmp_path / "scenes"
    revised_dir = tmp_path / "revised"
    packet_dir = tmp_path / "packets"
    scene_dir.mkdir()
    revised_dir.mkdir()
    packet_dir.mkdir()
    scene_one = scene_dir / "ch01_sc01.md"
    scene_two = scene_dir / "ch01_sc02.md"
    revised_one = revised_dir / "ch01_sc01_revised.md"
    revised_two = revised_dir / "ch01_sc02_revised.md"
    scene_one.write_text("Original first scene text.", encoding="utf-8")
    scene_two.write_text("Original second scene text.", encoding="utf-8")
    revised_one.write_text("Revised first scene text.", encoding="utf-8")
    revised_two.write_text("Revised second scene text.", encoding="utf-8")
    summary_path = tmp_path / "book_run_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "run_id": "run1",
                "book_id": "book1",
                "series_id": "series1",
                "scenes": [
                    {
                        "scene_id": "ch01_sc01",
                        "chapter_id": "1",
                        "output_path": str(scene_one),
                        "word_count": 4,
                    },
                    {
                        "scene_id": "ch01_sc02",
                        "chapter_id": "1",
                        "output_path": str(scene_two),
                        "word_count": 4,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    backlog_path = tmp_path / "book_revision_backlog.json"
    backlog_path.write_text(
        json.dumps(
            {
                "schema_version": "revision_backlog.v1",
                "summary_path": str(summary_path),
                "run_id": "run1",
                "book_id": "book1",
                "series_id": "series1",
            }
        ),
        encoding="utf-8",
    )
    packet_manifest_path = packet_dir / "revision_packet_manifest.json"
    packet_manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "targeted_revision_packet_manifest.v1",
                "source_backlog_path": str(backlog_path),
                "source_run_id": "run1",
                "book_id": "book1",
                "series_id": "series1",
                "packets": [],
            }
        ),
        encoding="utf-8",
    )
    comparison_path = tmp_path / "targeted_revision_comparison.json"
    scene_results = [
        _comparison_scene_result("ch01_sc01", revised_one, result_passed_by_scene["ch01_sc01"])
    ]
    if "ch01_sc02" in result_passed_by_scene:
        scene_results.append(
            _comparison_scene_result("ch01_sc02", revised_two, result_passed_by_scene["ch01_sc02"])
        )
    comparison_path.write_text(
        json.dumps(
            {
                "schema_version": "targeted_revision_comparison.v1",
                "packet_manifest_path": str(packet_manifest_path),
                "source_run_id": "run1",
                "book_id": "book1",
                "series_id": "series1",
                "passed": comparison_passed,
                "failed_scene_ids": [
                    scene_id for scene_id, passed in result_passed_by_scene.items() if not passed
                ],
                "scene_results": scene_results,
            }
        ),
        encoding="utf-8",
    )
    return {
        "comparison": comparison_path,
        "scene_one": scene_one,
        "scene_two": scene_two,
    }


def _comparison_scene_result(scene_id: str, revised_path: Path, passed: bool) -> dict[str, object]:
    return {
        "scene_id": scene_id,
        "chapter_id": "1",
        "revised_path": str(revised_path),
        "passed": passed,
        "checks": {"stub": passed},
        "current_metrics": {},
        "revised_metrics": {},
        "deltas": {},
        "phrase_results": [],
        "notes": [] if passed else ["failed"],
    }
