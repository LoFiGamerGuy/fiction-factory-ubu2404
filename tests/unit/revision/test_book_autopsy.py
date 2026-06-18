"""Offline book-run autopsy and targeted revision planning tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pipeline.ledgers.book_metrics_ledger import BookMetricsEvent, BookMetricsLedger
from pipeline.revision.book_autopsy import build_book_revision_backlog, detect_repeated_phrases
from pipeline.revision.models import AnalyzedScene


def test_build_book_revision_backlog_reads_run_artifacts(tmp_path: Path) -> None:
    book_id = "book1"
    series_id = "series1"
    ledger_root = tmp_path / "ledgers"
    scene_dir = tmp_path / "scenes"
    scene_dir.mkdir()
    scene_one = scene_dir / "ch01_sc01.md"
    scene_two = scene_dir / "ch01_sc02.md"
    scene_one.write_text(
        "Salt wind promise. Salt wind promise. Salt wind promise. Salt wind promise.\n"
        'Sarah: "Can we repair the inn?"\n',
        encoding="utf-8",
    )
    scene_two.write_text(
        "Salt wind promise. Salt wind promise. Salt wind promise. Salt wind promise.\n"
        'Miles: "We should decide before the inspection."\n',
        encoding="utf-8",
    )

    metrics_ledger = BookMetricsLedger(book_id, data_root=ledger_root)
    metrics_ledger.append(
        _metrics_event(
            book_id=book_id,
            scene_id="ch01_sc01",
            chapter_id="1",
            word_count=800,
            dialogue_ratio=0.10,
        )
    )
    metrics_ledger.append(
        _metrics_event(
            book_id=book_id,
            scene_id="ch01_sc02",
            chapter_id="1",
            word_count=1200,
            dialogue_ratio=0.30,
        )
    )
    metrics_ledger.close()

    trace_root = ledger_root / series_id / "traces"
    trace_root.mkdir(parents=True)
    (trace_root / "ch01_sc01.json").write_text(
        json.dumps(
            {
                "quality_scores": {
                    "structural_weighted_points": 10,
                    "metric_word_count": 800,
                }
            }
        ),
        encoding="utf-8",
    )

    summary_path = tmp_path / "book_run_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "run_id": "run1",
                "book_id": book_id,
                "series_id": series_id,
                "run_passed": True,
                "ledger_data_root": str(ledger_root),
                "ledger_dashboard_summary": {
                    "scene_rhythm": ["dialogue", "dialogue", "dialogue", "dialogue", "dialogue"],
                    "intimacy_pairs": {},
                    "promises_critical_open": 0,
                },
                "eval_status": {
                    "scenes": [
                        {
                            "scene_path": str(scene_one),
                            "voice_consistency": 0.90,
                            "ai_tell": 0.60,
                        },
                        {
                            "scene_path": str(scene_two),
                            "voice_consistency": 0.95,
                            "ai_tell": 0.90,
                        },
                    ]
                },
                "scenes": [
                    {
                        "scene_id": "ch01_sc01",
                        "chapter_id": "1",
                        "output_path": str(scene_one),
                        "word_count": 800,
                        "adjusted_word_count_target": 1000,
                        "revise_count": 2,
                        "force_resolved": False,
                    },
                    {
                        "scene_id": "ch01_sc02",
                        "chapter_id": "1",
                        "output_path": str(scene_two),
                        "word_count": 1200,
                        "adjusted_word_count_target": 1000,
                        "revise_count": 0,
                        "force_resolved": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    backlog = build_book_revision_backlog(summary_path, target_scene_count=1)

    assert backlog["schema_version"] == "revision_backlog.v1"
    assert backlog["run_id"] == "run1"
    assert backlog["scene_count"] == 2
    assert backlog["issue_count"] > 0
    assert backlog["issue_counts_by_category"]["scene_rhythm"] == 1
    assert backlog["issue_counts_by_category"]["character_arc"] == 1
    assert backlog["issue_counts_by_category"]["ai_tell_density"] == 1
    assert backlog["issue_counts_by_category"]["structural_density"] == 1
    assert "salt wind promise" in backlog["repeated_phrases"]
    plan = backlog["targeted_revision_plan"]
    assert plan["status"] == "planned_no_live"
    assert plan["target_scene_count"] == 1
    assert plan["scenes"][0]["scene_id"] == "ch01_sc01"
    assert plan["scenes"][0]["current_scene_path"] == str(scene_one)


def test_detect_repeated_phrases_requires_multiple_scenes() -> None:
    scenes = [
        AnalyzedScene(
            scene_id="scene1",
            chapter_id="1",
            output_path="scene1.md",
            text="Harbor light flickered. Harbor light flickered.",
            status_word_count=6,
            adjusted_word_count_target=10,
            revise_count=0,
            force_resolved=False,
        ),
        AnalyzedScene(
            scene_id="scene2",
            chapter_id="1",
            output_path="scene2.md",
            text="Harbor light flickered. Harbor light flickered.",
            status_word_count=6,
            adjusted_word_count_target=10,
            revise_count=0,
            force_resolved=False,
        ),
    ]

    repeated = detect_repeated_phrases(scenes, min_count=4)

    assert repeated == {"harbor light flickered": ["scene1", "scene2"]}


def _metrics_event(
    *,
    book_id: str,
    scene_id: str,
    chapter_id: str,
    word_count: int,
    dialogue_ratio: float,
) -> BookMetricsEvent:
    return BookMetricsEvent(
        event_id=f"event-{scene_id}",
        book_id=book_id,
        chapter_id=chapter_id,
        scene_id=scene_id,
        timestamp=datetime.now(UTC).isoformat(),
        word_count=word_count,
        interiority_pct=0.20,
        dialogue_ratio=dialogue_ratio,
        exposition_pct=0.10,
        action_pct=0.25,
        sensory_density_per_1k=5.0,
        em_dash_density=0.0,
        sentence_length_avg=12.0,
        ai_tell_count=1,
        no_fly_violations=0,
        heat_curve_position=0.2,
        sex_scene_flag=False,
    )
