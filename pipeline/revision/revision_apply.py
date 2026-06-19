"""Apply accepted targeted revision outputs into a separate manuscript variant."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


class RevisionApplicationError(RuntimeError):
    """Raised when a revision comparison cannot be safely applied."""


def apply_revision_outputs(
    comparison_path: Path,
    output_dir: Path,
    *,
    allow_partial: bool = False,
    summary_path: Path | None = None,
) -> dict[str, Any]:
    """Apply accepted revisions and assemble a no-live revised manuscript variant."""
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    comparison_passed = bool(comparison.get("passed"))
    if not comparison_passed and not allow_partial:
        failed = ", ".join(str(value) for value in comparison.get("failed_scene_ids", []))
        raise RevisionApplicationError(
            "Revision comparison failed; refusing to apply revisions without --allow-partial. "
            f"Failed scenes: {failed or 'unknown'}"
        )

    resolved_summary_path = summary_path or _resolve_summary_path(comparison)
    summary = json.loads(resolved_summary_path.read_text(encoding="utf-8"))
    scene_rows = _sequence(summary.get("scenes"))
    if not scene_rows:
        raise RevisionApplicationError(f"No scenes found in summary: {resolved_summary_path}")

    accepted_results = [
        row for row in _sequence(comparison.get("scene_results")) if row.get("passed")
    ]
    if not accepted_results:
        raise RevisionApplicationError("No accepted revised scenes found in comparison report.")

    output_dir.mkdir(parents=True, exist_ok=True)
    accepted_dir = output_dir / "accepted_revisions"
    accepted_dir.mkdir(parents=True, exist_ok=True)

    summary_scene_ids = {str(row.get("scene_id", "")) for row in scene_rows}
    accepted_by_scene = _copy_accepted_revisions(accepted_results, accepted_dir, summary_scene_ids)
    manuscript_path = output_dir / "manuscript_revised.md"
    assembly = _assemble_revised_manuscript(
        scene_rows=scene_rows,
        replacements=accepted_by_scene,
        book_id=str(summary.get("book_id") or comparison.get("book_id") or "book"),
        manuscript_path=manuscript_path,
    )
    failed_scene_ids = [
        str(row.get("scene_id"))
        for row in _sequence(comparison.get("scene_results"))
        if not row.get("passed")
    ]
    report = {
        "schema_version": "revision_application_summary.v1",
        "status": "applied_no_live" if comparison_passed else "partial_applied_no_live",
        "comparison_path": str(comparison_path),
        "summary_path": str(resolved_summary_path),
        "source_run_id": comparison.get("source_run_id") or summary.get("run_id"),
        "book_id": summary.get("book_id") or comparison.get("book_id"),
        "series_id": summary.get("series_id") or comparison.get("series_id"),
        "comparison_passed": comparison_passed,
        "allow_partial": allow_partial,
        "original_scene_count": len(scene_rows),
        "applied_scene_count": len(accepted_by_scene),
        "applied_scene_ids": sorted(accepted_by_scene),
        "skipped_failed_scene_ids": failed_scene_ids,
        "accepted_revisions_dir": str(accepted_dir),
        "manuscript_path": str(manuscript_path),
        "total_word_count": assembly["total_word_count"],
        "scenes": assembly["scenes"],
    }
    summary_output = output_dir / "revision_application_summary.json"
    summary_output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    report["application_summary_path"] = str(summary_output)
    summary_output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _resolve_summary_path(comparison: dict[str, Any]) -> Path:
    manifest_path = Path(str(comparison.get("packet_manifest_path", "")))
    if not manifest_path.exists():
        raise RevisionApplicationError(
            f"Cannot resolve summary path because packet manifest is missing: {manifest_path}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    backlog_raw = str(manifest.get("source_backlog_path", ""))
    backlog_path = _resolve_path(backlog_raw, manifest_path.parent)
    if not backlog_path.exists():
        raise RevisionApplicationError(
            f"Cannot resolve summary path; backlog missing: {backlog_path}"
        )
    backlog = json.loads(backlog_path.read_text(encoding="utf-8"))
    summary_raw = str(backlog.get("summary_path", ""))
    if not summary_raw:
        raise RevisionApplicationError(
            "Backlog does not contain summary_path; pass --summary-path."
        )
    summary_path = _resolve_path(summary_raw, backlog_path.parent)
    if not summary_path.exists():
        raise RevisionApplicationError(f"Summary not found: {summary_path}")
    return summary_path


def _copy_accepted_revisions(
    accepted_results: list[dict[str, Any]],
    accepted_dir: Path,
    summary_scene_ids: set[str],
) -> dict[str, Path]:
    accepted_by_scene: dict[str, Path] = {}
    for result in accepted_results:
        scene_id = str(result.get("scene_id", ""))
        if scene_id not in summary_scene_ids:
            raise RevisionApplicationError(
                f"Accepted revised scene is not present in source summary: {scene_id}"
            )
        revised_path = Path(str(result.get("revised_path", "")))
        if not revised_path.exists():
            raise RevisionApplicationError(f"Accepted revised scene missing: {revised_path}")
        target_path = accepted_dir / f"{scene_id}.md"
        shutil.copyfile(revised_path, target_path)
        accepted_by_scene[scene_id] = target_path
    return accepted_by_scene


def _assemble_revised_manuscript(
    *,
    scene_rows: list[dict[str, Any]],
    replacements: dict[str, Path],
    book_id: str,
    manuscript_path: Path,
) -> dict[str, Any]:
    parts: list[str] = [f"# {book_id}"]
    scenes: list[dict[str, Any]] = []
    total_word_count = 0
    current_chapter: str | None = None
    for row in scene_rows:
        scene_id = str(row.get("scene_id", ""))
        chapter_id = str(row.get("chapter_id", ""))
        source = "revised" if scene_id in replacements else "original"
        source_path = replacements.get(scene_id) or Path(str(row.get("output_path", "")))
        if not source_path.exists():
            raise RevisionApplicationError(f"Missing scene text for {scene_id}: {source_path}")
        text = source_path.read_text(encoding="utf-8").strip()
        word_count = len(text.split())
        total_word_count += word_count

        if chapter_id != current_chapter:
            parts.append(f"## Chapter {chapter_id}")
            current_chapter = chapter_id
        parts.append(f"### Scene {scene_id}")
        parts.append(text)
        scenes.append(
            {
                "scene_id": scene_id,
                "chapter_id": chapter_id,
                "source": source,
                "source_path": str(source_path),
                "word_count": word_count,
            }
        )

    manuscript_path.write_text("\n\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return {"total_word_count": total_word_count, "scenes": scenes}


def _resolve_path(raw_path: str, base_dir: Path) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else (base_dir / path).resolve()


def _sequence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
