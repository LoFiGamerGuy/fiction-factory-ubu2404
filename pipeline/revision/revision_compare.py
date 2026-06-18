"""No-live comparison of targeted revision outputs against packets."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pipeline.agents.scanner import NoFlyScanner
from pipeline.agents.structural_analysis import StructuralAnalyzer

_WORD_RE = re.compile(r"\b\w+(?:'\w+)?\b")
_MARKDOWN_SEPARATOR_RE = re.compile(r"(?m)^\s*-{3,}\s*$")
_ALTERNATE_VERSION_RE = re.compile(
    r"\b(alternate version|version \d+|revised version)\b", re.IGNORECASE
)


def compare_revision_outputs(
    packet_manifest_path: Path,
    revised_dir: Path,
    *,
    nofly_catalog_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Compare revised scene files against targeted revision packets."""
    manifest = json.loads(packet_manifest_path.read_text(encoding="utf-8"))
    scanner = NoFlyScanner(nofly_catalog_path)
    scene_results = [
        _compare_packet_row(row, revised_dir, scanner) for row in _sequence(manifest.get("packets"))
    ]
    passed = bool(scene_results) and all(bool(result.get("passed")) for result in scene_results)
    report = {
        "schema_version": "targeted_revision_comparison.v1",
        "packet_manifest_path": str(packet_manifest_path),
        "revised_dir": str(revised_dir),
        "source_run_id": manifest.get("source_run_id"),
        "book_id": manifest.get("book_id"),
        "series_id": manifest.get("series_id"),
        "scene_count": len(scene_results),
        "passed": passed,
        "failed_scene_ids": [
            str(result.get("scene_id")) for result in scene_results if not result.get("passed")
        ],
        "scene_results": scene_results,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _compare_packet_row(
    row: dict[str, Any], revised_dir: Path, scanner: NoFlyScanner
) -> dict[str, Any]:
    packet_path = Path(str(row.get("json_path", "")))
    if not packet_path.exists():
        scene_id = str(row.get("scene_id", ""))
        return _missing_result(scene_id, f"Packet not found: {packet_path}")

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    scene_id = str(packet.get("scene_id", ""))
    revised_path = _find_revised_scene(revised_dir, scene_id)
    if revised_path is None:
        return _missing_result(scene_id, f"Revised scene not found under {revised_dir}")

    current_text = _read_current_text(packet)
    revised_text = revised_path.read_text(encoding="utf-8")
    current_metrics = _scene_metrics(current_text, scanner)
    revised_metrics = _scene_metrics(revised_text, scanner)
    phrase_results = _phrase_results(packet, current_text, revised_text)
    checks = _checks(
        packet, current_text, revised_text, current_metrics, revised_metrics, phrase_results
    )
    passed = all(bool(value) for value in checks.values())
    return {
        "scene_id": scene_id,
        "chapter_id": packet.get("chapter_id"),
        "packet_path": str(packet_path),
        "revised_path": str(revised_path),
        "passed": passed,
        "checks": checks,
        "current_metrics": current_metrics,
        "revised_metrics": revised_metrics,
        "deltas": _metric_deltas(current_metrics, revised_metrics),
        "phrase_results": phrase_results,
        "notes": _notes(checks),
    }


def _checks(
    packet: dict[str, Any],
    current_text: str,
    revised_text: str,
    current_metrics: dict[str, Any],
    revised_metrics: dict[str, Any],
    phrase_results: list[dict[str, Any]],
) -> dict[str, bool]:
    categories = {str(issue.get("category")) for issue in _sequence(packet.get("issues"))}
    target = int(packet.get("adjusted_word_count_target") or 0)
    lower = round(target * 0.9) if target > 0 else 0
    upper = round(target * 1.15) if target > 0 else 0
    revised_word_count = int(revised_metrics["word_count"])
    requires_structural = bool(categories & {"ai_tell_density", "structural_density"})
    return {
        "current_hash_matches_packet": _sha1(current_text)
        == str(packet.get("current_scene_sha1", "")),
        "revised_scene_nonempty": bool(revised_text.strip()),
        "word_count_in_target_band": target <= 0 or lower <= revised_word_count <= upper,
        "no_markdown_separator_appendix": not _has_markdown_appendix(revised_text),
        "structural_weight_not_worse": (not requires_structural)
        or int(revised_metrics["structural_weighted_score"])
        <= int(current_metrics["structural_weighted_score"]),
        "no_fly_violations_not_worse": int(revised_metrics["no_fly_violations"])
        <= int(current_metrics["no_fly_violations"]),
        "ai_tell_score_not_worse": (not requires_structural)
        or float(revised_metrics["ai_tell_score"]) >= float(current_metrics["ai_tell_score"]),
        "repeated_phrases_reduced": all(bool(result.get("improved")) for result in phrase_results),
    }


def _scene_metrics(text: str, scanner: NoFlyScanner) -> dict[str, Any]:
    words = _WORD_RE.findall(text)
    word_count = len(words)
    structural = StructuralAnalyzer().analyze(text)
    no_fly = scanner.scan(text)
    weighted = structural.weighted_score()
    density = weighted / max(1.0, word_count / 1000.0)
    return {
        "word_count": word_count,
        "no_fly_violations": no_fly.total_violations,
        "no_fly_critical_count": no_fly.critical_count,
        "no_fly_high_count": no_fly.high_count,
        "structural_issue_count": structural.total,
        "structural_weighted_score": weighted,
        "structural_weighted_density_per_1k": round(density, 4),
        "ai_tell_score": round(max(0.0, 1.0 - density / 10.0), 4),
    }


def _metric_deltas(
    current_metrics: dict[str, Any], revised_metrics: dict[str, Any]
) -> dict[str, Any]:
    return {
        "word_count": int(revised_metrics["word_count"]) - int(current_metrics["word_count"]),
        "structural_issue_count": int(revised_metrics["structural_issue_count"])
        - int(current_metrics["structural_issue_count"]),
        "no_fly_violations": int(revised_metrics["no_fly_violations"])
        - int(current_metrics["no_fly_violations"]),
        "structural_weighted_score": int(revised_metrics["structural_weighted_score"])
        - int(current_metrics["structural_weighted_score"]),
        "ai_tell_score": round(
            float(revised_metrics["ai_tell_score"]) - float(current_metrics["ai_tell_score"]),
            4,
        ),
    }


def _phrase_results(
    packet: dict[str, Any], current_text: str, revised_text: str
) -> list[dict[str, Any]]:
    results = []
    for issue in _sequence(packet.get("issues")):
        if issue.get("category") != "repeated_phrase":
            continue
        phrase = str(_mapping(issue.get("metadata")).get("phrase", ""))
        before_count = _phrase_count(current_text, phrase)
        after_count = _phrase_count(revised_text, phrase)
        results.append(
            {
                "issue_id": issue.get("issue_id"),
                "phrase": phrase,
                "before_count": before_count,
                "after_count": after_count,
                "improved": before_count == 0 or after_count < before_count,
            }
        )
    return results


def _phrase_count(text: str, phrase: str) -> int:
    if not phrase:
        return 0
    pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE)
    return len(pattern.findall(text))


def _read_current_text(packet: dict[str, Any]) -> str:
    current_path = Path(str(packet.get("current_scene_path", "")))
    if current_path.exists():
        return current_path.read_text(encoding="utf-8")
    return str(packet.get("current_text", ""))


def _find_revised_scene(revised_dir: Path, scene_id: str) -> Path | None:
    candidates = (
        revised_dir / f"{scene_id}_revised.md",
        revised_dir / f"{scene_id}.md",
        revised_dir / f"{scene_id}_revised.txt",
        revised_dir / f"{scene_id}.txt",
    )
    return next((path for path in candidates if path.exists()), None)


def _has_markdown_appendix(text: str) -> bool:
    return bool(_MARKDOWN_SEPARATOR_RE.search(text) or _ALTERNATE_VERSION_RE.search(text))


def _notes(checks: dict[str, bool]) -> list[str]:
    labels = {
        "current_hash_matches_packet": "Current source scene changed since packet creation.",
        "revised_scene_nonempty": "Revised scene is empty or missing.",
        "word_count_in_target_band": "Revised word count is outside packet target band.",
        "no_markdown_separator_appendix": "Revised scene contains a Markdown appendix/separator.",
        "structural_weight_not_worse": "Structural weighted score worsened.",
        "no_fly_violations_not_worse": "No-fly scanner violations worsened.",
        "ai_tell_score_not_worse": "AI-tell score worsened.",
        "repeated_phrases_reduced": "One or more repeated phrases were not reduced.",
    }
    return [labels[key] for key, passed in checks.items() if not passed]


def _missing_result(scene_id: str, note: str) -> dict[str, Any]:
    return {
        "scene_id": scene_id,
        "passed": False,
        "checks": {"revised_scene_nonempty": False},
        "current_metrics": {},
        "revised_metrics": {},
        "deltas": {},
        "phrase_results": [],
        "notes": [note],
    }


def _sha1(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _sequence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
