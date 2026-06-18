"""No-live targeted revision packet generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def build_targeted_revision_packets(
    backlog_path: Path,
    output_dir: Path,
    *,
    include_current_text: bool = True,
    max_scene_chars: int = 12000,
) -> dict[str, Any]:
    """Write per-scene JSON/Markdown revision packets from a backlog file."""
    backlog = json.loads(backlog_path.read_text(encoding="utf-8"))
    plan = _mapping(backlog.get("targeted_revision_plan"))
    output_dir.mkdir(parents=True, exist_ok=True)

    issue_rows = [_mapping(issue) for issue in _sequence(backlog.get("issues"))]
    issues_by_id = {str(issue.get("issue_id")): issue for issue in issue_rows}
    global_issues = [issue for issue in issue_rows if _is_global_book_issue(issue)]
    packets: list[dict[str, Any]] = []

    for selected in _sequence(plan.get("scenes")):
        scene_id = str(selected.get("scene_id", ""))
        direct_issues = [
            issues_by_id[issue_id]
            for issue_id in [str(value) for value in selected.get("issue_ids", [])]
            if issue_id in issues_by_id
        ]
        cross_scene_issues = [
            issue for issue in issue_rows if _book_issue_mentions_scene(issue, scene_id)
        ]
        issues = _dedupe_issues([*direct_issues, *cross_scene_issues])
        current_scene_path = Path(str(selected.get("current_scene_path", "")))
        source_text = _read_scene_text(current_scene_path)
        embedded_text = _truncate_scene_text(source_text, max_scene_chars=max_scene_chars)
        packet = _build_packet(
            backlog=backlog,
            selected=selected,
            issues=issues,
            global_issues=global_issues,
            source_text=source_text,
            current_text=embedded_text if include_current_text else "",
            include_current_text=include_current_text,
            backlog_path=backlog_path,
        )
        json_path = output_dir / f"{scene_id}_revision_packet.json"
        markdown_path = output_dir / f"{scene_id}_revision_packet.md"
        json_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(_packet_markdown(packet), encoding="utf-8")
        packets.append(
            {
                "scene_id": scene_id,
                "chapter_id": selected.get("chapter_id"),
                "severity_total": selected.get("severity_total", 0),
                "issue_count": len(packet["issues"]),
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            }
        )

    manifest = {
        "schema_version": "targeted_revision_packet_manifest.v1",
        "source_backlog_path": str(backlog_path),
        "source_run_id": plan.get("source_run_id") or backlog.get("run_id"),
        "book_id": backlog.get("book_id"),
        "series_id": backlog.get("series_id"),
        "packet_count": len(packets),
        "packets": packets,
    }
    manifest_path = output_dir / "revision_packet_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _build_packet(
    *,
    backlog: dict[str, Any],
    selected: dict[str, Any],
    issues: list[dict[str, Any]],
    global_issues: list[dict[str, Any]],
    source_text: str,
    current_text: str,
    include_current_text: bool,
    backlog_path: Path,
) -> dict[str, Any]:
    scene_id = str(selected.get("scene_id", ""))
    return {
        "schema_version": "targeted_revision_packet.v1",
        "source_backlog_path": str(backlog_path),
        "source_run_id": backlog.get("run_id"),
        "book_id": backlog.get("book_id"),
        "series_id": backlog.get("series_id"),
        "scene_id": scene_id,
        "chapter_id": selected.get("chapter_id"),
        "current_scene_path": selected.get("current_scene_path"),
        "current_scene_sha1": _sha1(source_text),
        "current_word_count": selected.get("current_word_count", 0),
        "adjusted_word_count_target": selected.get("adjusted_word_count_target", 0),
        "severity_total": selected.get("severity_total", 0),
        "issues": issues,
        "book_level_context": global_issues,
        "revision_objectives": _revision_objectives(issues),
        "constraints": _revision_constraints(selected),
        "current_text_included": include_current_text,
        "current_text": current_text,
        "output_contract": {
            "status": "packet_only_no_live",
            "expected_artifacts": [
                f"{scene_id}_revised.md",
                f"{scene_id}_revision_notes.json",
            ],
            "must_preserve": ["scene_id", "chapter_id", "story continuity", "content policy"],
        },
    }


def _revision_objectives(issues: list[dict[str, Any]]) -> list[str]:
    objectives: list[str] = []
    for issue in issues:
        category = str(issue.get("category", ""))
        recommendation = str(issue.get("recommendation", "")).strip()
        if category == "ai_tell_density":
            objectives.append(
                "Reduce AI-tell density by replacing abstractions, explanations, and "
                "summary emotion labels with concrete action/subtext."
            )
        elif category == "structural_density":
            objectives.append("Lower weighted structural flag density without shrinking the scene.")
        elif category == "word_budget":
            objectives.append("Bring the scene closer to its adjusted word target.")
        elif category == "dialogue_balance":
            objectives.append("Add or sharpen conflict-bearing dialogue where it serves the beat.")
        elif category == "convergence":
            objectives.append(
                "Resolve quality-loop friction while preserving the approved scene outcome."
            )
        elif category == "repeated_phrase":
            phrase = _mapping(issue.get("metadata")).get("phrase")
            objectives.append(f"Vary or cut repeated phrase: {phrase!r}.")
        elif recommendation:
            objectives.append(recommendation)
    return _dedupe_strings(objectives)


def _revision_constraints(selected: dict[str, Any]) -> list[str]:
    target = int(selected.get("adjusted_word_count_target") or 0)
    lower = round(target * 0.9) if target > 0 else 0
    upper = round(target * 1.15) if target > 0 else 0
    constraints = [
        "Do not loosen Sensitivity Profile or content-policy constraints.",
        "Do not introduce new unresolved promises unless the scene brief requires them.",
        "Preserve current continuity facts unless the revision packet explicitly says otherwise.",
        "Do not add Markdown separators or alternate-version appendices to the revised scene.",
    ]
    if target > 0:
        constraints.append(
            f"Aim for {target} words; acceptable revision band is roughly {lower}-{upper} words."
        )
    return constraints


def _packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# Revision Packet: {packet['scene_id']}",
        "",
        f"Source run: `{packet.get('source_run_id')}`",
        f"Book: `{packet.get('series_id')}/{packet.get('book_id')}`",
        f"Current scene: `{packet.get('current_scene_path')}`",
        f"Current words: `{packet.get('current_word_count')}`",
        f"Adjusted target: `{packet.get('adjusted_word_count_target')}`",
        "",
        "## Objectives",
        *_bullet_lines(packet.get("revision_objectives", [])),
        "",
        "## Scene Issues",
        *_issue_lines(packet.get("issues", [])),
        "",
        "## Book-Level Context",
        *_issue_lines(packet.get("book_level_context", [])),
        "",
        "## Constraints",
        *_bullet_lines(packet.get("constraints", [])),
        "",
        "## Current Text",
        "",
        packet.get("current_text") or "Current text omitted by packet-generation option.",
        "",
    ]
    return "\n".join(lines)


def _issue_lines(issues: Any) -> list[str]:
    rows = [_mapping(issue) for issue in issues] if isinstance(issues, list) else []
    if not rows:
        return ["- None."]
    return [
        "- "
        f"`{issue.get('issue_id')}` "
        f"severity {issue.get('severity')}: {issue.get('signal')} - "
        f"{issue.get('recommendation')}"
        for issue in rows
    ]


def _bullet_lines(values: Any) -> list[str]:
    rows = [str(value) for value in values] if isinstance(values, list) else []
    return [f"- {value}" for value in rows] if rows else ["- None."]


def _read_scene_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _truncate_scene_text(text: str, *, max_scene_chars: int) -> str:
    if max_scene_chars > 0 and len(text) > max_scene_chars:
        return text[:max_scene_chars] + "\n\n[TRUNCATED BY PACKET BUILDER]"
    return text


def _is_global_book_issue(issue: dict[str, Any]) -> bool:
    return str(issue.get("scope")) == "book" and not _metadata_scene_ids(issue)


def _book_issue_mentions_scene(issue: dict[str, Any], scene_id: str) -> bool:
    return scene_id in _metadata_scene_ids(issue)


def _metadata_scene_ids(issue: dict[str, Any]) -> set[str]:
    metadata = _mapping(issue.get("metadata"))
    raw_scene_ids = metadata.get("scene_ids", [])
    if not isinstance(raw_scene_ids, list):
        return set()
    return {str(value) for value in raw_scene_ids}


def _dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped = []
    for issue in issues:
        issue_id = str(issue.get("issue_id", ""))
        if issue_id in seen:
            continue
        seen.add(issue_id)
        deduped.append(issue)
    return deduped


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _sha1(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _sequence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
