"""Book-run autopsy and revision backlog generation."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pipeline.agents.book_review_agents import default_book_reviewers
from pipeline.revision.models import (
    AnalyzedScene,
    BookRunContext,
    RevisionIssue,
    sort_issues,
)

_STOPWORDS = {
    "the",
    "and",
    "but",
    "that",
    "with",
    "from",
    "into",
    "this",
    "were",
    "there",
    "their",
    "they",
    "them",
    "then",
    "when",
    "what",
    "would",
    "could",
    "should",
    "because",
    "through",
}


def build_book_revision_backlog(
    summary_path: Path,
    *,
    target_scene_count: int = 10,
) -> dict[str, Any]:
    """Return a JSON-serializable autopsy and revision backlog payload."""
    context = load_book_run_context(summary_path)
    issues: list[RevisionIssue] = []
    for reviewer in default_book_reviewers():
        issues.extend(reviewer.review(context))
    sorted_issues = sort_issues(issues)
    issue_dicts = [issue.to_dict() for issue in sorted_issues]
    targeted_plan = build_targeted_revision_plan(
        context=context,
        issues=sorted_issues,
        target_scene_count=target_scene_count,
    )
    summary = context.summary
    return {
        "schema_version": "revision_backlog.v1",
        "summary_path": str(summary_path),
        "run_id": summary.get("run_id"),
        "book_id": summary.get("book_id"),
        "series_id": summary.get("series_id"),
        "run_passed": summary.get("run_passed"),
        "scene_count": len(context.scenes),
        "issue_count": len(issue_dicts),
        "issues": issue_dicts,
        "issue_counts_by_category": _issue_counts(issue_dicts, "category"),
        "issue_counts_by_source": _issue_counts(issue_dicts, "source"),
        "narrative_counts": dict(context.narrative_counts),
        "repeated_phrases": {key: list(value) for key, value in context.repeated_phrases.items()},
        "targeted_revision_plan": targeted_plan,
    }


def load_book_run_context(summary_path: Path) -> BookRunContext:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    scenes = _load_scenes(summary)
    repeated_phrases = detect_repeated_phrases(scenes)
    ledger_dashboard = _mapping(summary.get("ledger_dashboard_summary"))
    narrative_counts = _load_narrative_counts(summary)
    return BookRunContext(
        summary_path=str(summary_path),
        summary=summary,
        scenes=scenes,
        ledger_dashboard=ledger_dashboard,
        narrative_counts=narrative_counts,
        repeated_phrases=repeated_phrases,
    )


def build_targeted_revision_plan(
    *,
    context: BookRunContext,
    issues: Sequence[RevisionIssue],
    target_scene_count: int,
) -> dict[str, Any]:
    """Select the worst scenes and produce a no-live targeted revision plan."""
    severity_by_scene: dict[str, int] = {}
    issue_ids_by_scene: dict[str, list[str]] = {}
    for issue in issues:
        if issue.scene_id is None:
            continue
        severity_by_scene[issue.scene_id] = (
            severity_by_scene.get(issue.scene_id, 0) + issue.severity
        )
        issue_ids_by_scene.setdefault(issue.scene_id, []).append(issue.issue_id)

    scene_by_id = {scene.scene_id: scene for scene in context.scenes}
    selected_ids = sorted(
        severity_by_scene,
        key=lambda scene_id: (-severity_by_scene[scene_id], scene_id),
    )[:target_scene_count]
    selected = []
    for scene_id in selected_ids:
        scene = scene_by_id[scene_id]
        selected.append(
            {
                "scene_id": scene_id,
                "chapter_id": scene.chapter_id,
                "severity_total": severity_by_scene[scene_id],
                "issue_ids": issue_ids_by_scene.get(scene_id, []),
                "current_scene_path": scene.output_path,
                "current_word_count": scene.status_word_count,
                "adjusted_word_count_target": scene.adjusted_word_count_target,
            }
        )
    return {
        "schema_version": "targeted_revision_plan.v1",
        "source_run_id": context.summary.get("run_id"),
        "target_scene_count": len(selected),
        "selection_strategy": "highest_sum_issue_severity",
        "status": "planned_no_live",
        "scenes": selected,
        "next_step": (
            "Build targeted revision packets for these scene IDs, then revise, "
            "reassemble, and compare against this backlog."
        ),
    }


def detect_repeated_phrases(
    scenes: Sequence[AnalyzedScene],
    *,
    min_count: int = 4,
    max_phrases: int = 12,
) -> dict[str, list[str]]:
    phrase_scenes: dict[str, set[str]] = {}
    phrase_counts: dict[str, int] = {}
    for scene in scenes:
        words = [word.lower() for word in re.findall(r"\b[a-zA-Z][a-zA-Z']+\b", scene.text)]
        for size in (3, 4):
            for index in range(0, max(0, len(words) - size + 1)):
                phrase_words = words[index : index + size]
                if phrase_words[0] in _STOPWORDS or phrase_words[-1] in _STOPWORDS:
                    continue
                if sum(1 for word in phrase_words if word in _STOPWORDS) > 1:
                    continue
                phrase = " ".join(phrase_words)
                phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
                phrase_scenes.setdefault(phrase, set()).add(scene.scene_id)

    repeated = [
        (phrase, phrase_counts[phrase], sorted(scene_ids))
        for phrase, scene_ids in phrase_scenes.items()
        if phrase_counts.get(phrase, 0) >= min_count and len(scene_ids) >= 2
    ]
    repeated.sort(key=lambda item: (-item[1], item[0]))
    return {phrase: scene_ids for phrase, _count, scene_ids in repeated[:max_phrases]}


def _load_scenes(summary: Mapping[str, Any]) -> list[AnalyzedScene]:
    eval_by_scene = _eval_by_scene(summary)
    trace_by_scene = _trace_by_scene(summary)
    metric_by_scene = _metric_by_scene(summary)
    scenes: list[AnalyzedScene] = []
    for raw_scene in _sequence(summary.get("scenes")):
        scene_id = str(raw_scene.get("scene_id", ""))
        output_path = str(raw_scene.get("output_path", ""))
        path = Path(output_path)
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        eval_row = eval_by_scene.get(scene_id, {})
        trace = trace_by_scene.get(scene_id, {})
        scenes.append(
            AnalyzedScene(
                scene_id=scene_id,
                chapter_id=str(raw_scene.get("chapter_id", "")),
                output_path=output_path,
                text=text,
                status_word_count=_int(raw_scene.get("word_count")),
                adjusted_word_count_target=_int(raw_scene.get("adjusted_word_count_target")),
                revise_count=_int(raw_scene.get("revise_count")),
                force_resolved=bool(raw_scene.get("force_resolved", False)),
                eval_voice_consistency=_optional_float(eval_row.get("voice_consistency")),
                eval_ai_tell=_optional_float(eval_row.get("ai_tell")),
                metrics=metric_by_scene.get(scene_id, {}),
                quality_scores=_quality_scores(trace),
            )
        )
    return scenes


def _eval_by_scene(summary: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    eval_status = _mapping(summary.get("eval_status"))
    for row in _sequence(eval_status.get("scenes")):
        scene_path = Path(str(row.get("scene_path", "")))
        result[scene_path.stem] = row
    return result


def _trace_by_scene(summary: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    ledger_root = Path(str(summary.get("ledger_data_root", "")))
    series_id = str(summary.get("series_id", ""))
    trace_root = ledger_root / series_id / "traces"
    traces: dict[str, Mapping[str, Any]] = {}
    if not trace_root.exists():
        return traces
    for path in trace_root.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        traces[path.stem] = payload
    return traces


def _metric_by_scene(summary: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    ledger_root = Path(str(summary.get("ledger_data_root", "")))
    book_id = str(summary.get("book_id", ""))
    db_path = ledger_root / book_id / "book_metrics.db"
    metrics: dict[str, Mapping[str, Any]] = {}
    if not db_path.exists():
        return metrics
    try:
        with sqlite3.connect(db_path) as connection:
            rows = connection.execute("select payload from events").fetchall()
    except sqlite3.Error:
        return metrics
    for (raw_payload,) in rows:
        payload = json.loads(str(raw_payload))
        scene_id = str(payload.get("scene_id", ""))
        metrics[scene_id] = _mapping(payload.get("metrics"))
    return metrics


def _load_narrative_counts(summary: Mapping[str, Any]) -> dict[str, int]:
    ledger_root = Path(str(summary.get("ledger_data_root", "")))
    book_id = str(summary.get("book_id", ""))
    series_id = str(summary.get("series_id", ""))
    return {
        "character_arc": _ledger_count(ledger_root / book_id / "character_arc.db"),
        "intimacy": _ledger_count(ledger_root / book_id / "intimacy_escalation.db"),
        "reader_info": _ledger_count(ledger_root / book_id / "reader_information_state.db"),
        "promise": _ledger_count(ledger_root / book_id / "promise.db"),
        "subplot": _ledger_count(ledger_root / book_id / "subplot.db"),
        "trope": _ledger_count(ledger_root / book_id / "trope_commitment.db"),
        "series_promise": _ledger_count(ledger_root / "series" / series_id / "series_promises.db"),
    }


def _ledger_count(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    try:
        with sqlite3.connect(db_path) as connection:
            row = connection.execute("select count(*) from events").fetchone()
    except sqlite3.Error:
        return 0
    return int(row[0]) if row is not None else 0


def _quality_scores(trace: Mapping[str, Any]) -> Mapping[str, float]:
    scores = _mapping(trace.get("quality_scores"))
    return {
        str(key): float(value) for key, value in scores.items() if isinstance(value, int | float)
    }


def _issue_counts(issues: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        value = str(issue.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _sequence(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
