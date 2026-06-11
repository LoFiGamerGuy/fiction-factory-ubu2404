"""Tests for short-book acceptance helper status builders."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pipeline.book_runner import BookRunResult, BookSceneStatus
from pipeline.core.managed_agent_config import ManagedAgentConfig
from pipeline.core.project_layout import ProjectLayout
from pipeline.memory.files_api_client import FilesAPIClient

book_acceptance = importlib.import_module("scripts.run_book_acceptance")


def _status(scene: Any, word_count: int = 450) -> BookSceneStatus:
    return BookSceneStatus(
        scene_id=scene.scene_id,
        chapter_id=scene.chapter_id,
        job_id=f"run_{scene.scene_id}",
        thread_id=f"run_{scene.scene_id}",
        status="completed",
        output_path=f"/tmp/{scene.scene_id}.md",
        convergence_decision="GO",
        revise_count=0,
        force_resolved=False,
        word_count=word_count,
        elapsed_seconds=1.0,
        started_at="2026-06-10T00:00:00+00:00",
        completed_at="2026-06-10T00:00:01+00:00",
        error="",
    )


def _result_for_total_words(
    scenes: tuple[Any, ...],
    total_word_count: int,
    *,
    model_tier: str = "test",
) -> BookRunResult:
    base_count = total_word_count // len(scenes)
    remainder = total_word_count % len(scenes)
    statuses = [
        _status(scene, word_count=base_count + (1 if index < remainder else 0))
        for index, scene in enumerate(scenes)
    ]
    return BookRunResult(
        run_id="fixture-run",
        book_id=book_acceptance.NOVELLA_BOOK_ID,
        series_id=book_acceptance.SERIES_ID,
        model_tier=model_tier,
        planned_scene_count=len(scenes),
        attempted_scene_count=len(scenes),
        successful_scenes=len(scenes),
        failed_scenes=0,
        go_scenes=len(scenes),
        force_resolved_scenes=0,
        skipped_scenes=0,
        previous_failed_scene_ids=[],
        elapsed_seconds=1.0,
        status_path="/tmp/status.jsonl",
        scenes=statuses,
    )


def test_short_book_verifier_status_passes_fixture_contract() -> None:
    spec = book_acceptance.create_short_book_spec()
    result = BookRunResult(
        run_id="fixture-run",
        book_id=spec.book_id,
        series_id=spec.series_id,
        model_tier="test",
        planned_scene_count=len(book_acceptance.DEFAULT_SCENES),
        attempted_scene_count=len(book_acceptance.DEFAULT_SCENES),
        successful_scenes=len(book_acceptance.DEFAULT_SCENES),
        failed_scenes=0,
        go_scenes=len(book_acceptance.DEFAULT_SCENES),
        force_resolved_scenes=0,
        skipped_scenes=0,
        previous_failed_scene_ids=[],
        elapsed_seconds=1.0,
        status_path="/tmp/status.jsonl",
        scenes=[_status(scene) for scene in book_acceptance.DEFAULT_SCENES],
    )

    status = book_acceptance.build_verifier_status(result, spec)

    assert status["passed"] is True
    assert status["failed_checks"] == []


def test_novella_verifier_status_passes_fixture_contract() -> None:
    spec = book_acceptance.create_fixture_spec("novella")
    scenes = book_acceptance.get_fixture_scenes("novella")
    result = BookRunResult(
        run_id="novella-fixture-run",
        book_id=spec.book_id,
        series_id=spec.series_id,
        model_tier="test",
        planned_scene_count=len(scenes),
        attempted_scene_count=len(scenes),
        successful_scenes=len(scenes),
        failed_scenes=0,
        go_scenes=len(scenes),
        force_resolved_scenes=0,
        skipped_scenes=0,
        previous_failed_scene_ids=[],
        elapsed_seconds=1.0,
        status_path="/tmp/status.jsonl",
        scenes=[_status(scene, word_count=383) for scene in scenes],
    )

    status = book_acceptance.build_verifier_status(result, spec, fixture="novella")

    assert len(scenes) == 12
    assert status["passed"] is True
    assert status["failed_checks"] == []


def test_novella_fixture_selection_uses_distinct_book_and_target() -> None:
    spec = book_acceptance.create_fixture_spec("novella")
    inventory = book_acceptance.create_fixture_inventory("novella")
    scenes = book_acceptance.get_fixture_scenes("novella")

    assert spec.book_id == book_acceptance.NOVELLA_BOOK_ID
    assert inventory.book_id == book_acceptance.NOVELLA_BOOK_ID
    assert inventory.word_count_target == book_acceptance.NOVELLA_WORD_COUNT_TARGET
    assert inventory.total_scenes == 12
    assert [scene.act for scene in scenes].count(1) == 3
    assert [scene.act for scene in scenes].count(2) == 6
    assert [scene.act for scene in scenes].count(3) == 3


def test_draft_acceptance_allows_production_style_surplus_but_verifier_fails() -> None:
    spec = book_acceptance.create_fixture_spec("novella")
    scenes = book_acceptance.get_fixture_scenes("novella")
    result = _result_for_total_words(scenes, 5464, model_tier="production")

    verifier_status = book_acceptance.build_verifier_status(result, spec, fixture="novella")
    draft_status = book_acceptance.build_draft_acceptance_status(
        result=result,
        target_word_count=book_acceptance.NOVELLA_WORD_COUNT_TARGET,
        actual_word_count=5464,
        eval_status={"passed": True},
        draft_surplus_allowed_pct=0.25,
    )

    assert verifier_status["passed"] is False
    assert verifier_status["failed_checks"][0]["check_name"] == "word_count"
    assert draft_status["passed"] is True
    assert draft_status["classification"] == "draft_surplus"
    assert draft_status["target_word_count"] == 4600
    assert draft_status["actual_word_count"] == 5464
    assert draft_status["surplus_words"] == 864
    assert draft_status["surplus_pct"] == 0.187826
    assert draft_status["draft_surplus_allowed_pct"] == 0.25
    assert draft_status["within_draft_surplus"] is True
    assert (
        book_acceptance.select_acceptance_passed(
            acceptance_mode="draft",
            draft_acceptance_status=draft_status,
            result=result,
            eval_status={"passed": True},
            verifier_status=verifier_status,
        )
        is True
    )


def test_draft_acceptance_rejects_surplus_beyond_ceiling() -> None:
    scenes = book_acceptance.get_fixture_scenes("novella")
    result = _result_for_total_words(scenes, 6000, model_tier="production")

    draft_status = book_acceptance.build_draft_acceptance_status(
        result=result,
        target_word_count=book_acceptance.NOVELLA_WORD_COUNT_TARGET,
        actual_word_count=6000,
        eval_status={"passed": True},
        draft_surplus_allowed_pct=0.25,
    )

    assert draft_status["passed"] is False
    assert draft_status["classification"] == "draft_failed"
    assert draft_status["surplus_words"] == 1400
    assert draft_status["surplus_pct"] == 0.304348
    assert draft_status["within_draft_surplus"] is False


def test_final_acceptance_mode_still_fails_when_verifier_fails() -> None:
    spec = book_acceptance.create_fixture_spec("novella")
    scenes = book_acceptance.get_fixture_scenes("novella")
    result = _result_for_total_words(scenes, 5464, model_tier="production")
    eval_status = {"passed": True}
    verifier_status = book_acceptance.build_verifier_status(result, spec, fixture="novella")
    draft_status = book_acceptance.build_draft_acceptance_status(
        result=result,
        target_word_count=book_acceptance.NOVELLA_WORD_COUNT_TARGET,
        actual_word_count=5464,
        eval_status=eval_status,
    )

    assert draft_status["passed"] is True
    assert (
        book_acceptance.select_acceptance_passed(
            acceptance_mode="final",
            draft_acceptance_status=draft_status,
            result=result,
            eval_status=eval_status,
            verifier_status=verifier_status,
        )
        is False
    )


def test_test_tier_novella_passes_draft_and_final_acceptance() -> None:
    spec = book_acceptance.create_fixture_spec("novella")
    scenes = book_acceptance.get_fixture_scenes("novella")
    result = _result_for_total_words(scenes, 4702)
    eval_status = {"passed": True}
    verifier_status = book_acceptance.build_verifier_status(result, spec, fixture="novella")
    draft_status = book_acceptance.build_draft_acceptance_status(
        result=result,
        target_word_count=book_acceptance.NOVELLA_WORD_COUNT_TARGET,
        actual_word_count=4702,
        eval_status=eval_status,
    )

    assert verifier_status["passed"] is True
    assert draft_status["passed"] is True
    assert draft_status["classification"] == "draft_surplus"
    assert (
        book_acceptance.select_acceptance_passed(
            acceptance_mode="draft",
            draft_acceptance_status=draft_status,
            result=result,
            eval_status=eval_status,
            verifier_status=verifier_status,
        )
        is True
    )
    assert (
        book_acceptance.select_acceptance_passed(
            acceptance_mode="final",
            draft_acceptance_status=draft_status,
            result=result,
            eval_status=eval_status,
            verifier_status=verifier_status,
        )
        is True
    )


def test_short_book_eval_status_uses_deterministic_suite(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    scene_dir = tmp_path / "scenes"
    scene_dir.mkdir()
    for scene in book_acceptance.DEFAULT_SCENES:
        (scene_dir / f"{scene.scene_id}.md").write_text(
            "Emma chose the next step.", encoding="utf-8"
        )

    fake_runs = [
        SimpleNamespace(
            scene_path=scene_dir / f"{scene.scene_id}.md",
            passed=True,
            voice=SimpleNamespace(score=0.9),
            ai_tell=SimpleNamespace(score=0.8),
        )
        for scene in book_acceptance.DEFAULT_SCENES
    ]
    monkeypatch.setattr(
        book_acceptance.run_eval,
        "evaluate_scenes",
        lambda **kwargs: SimpleNamespace(passed=True, scene_count=len(fake_runs), runs=fake_runs),
    )

    status = book_acceptance.build_eval_status(
        scene_dir=scene_dir,
        model_tier="test",
        voice_threshold=0.75,
        ai_tell_threshold=0.5,
    )

    assert status["passed"] is True
    assert status["scene_count"] == len(book_acceptance.DEFAULT_SCENES)
    assert status["required_scene_count"] == len(book_acceptance.DEFAULT_SCENES)
    assert status["scenes"][0]["voice_consistency"] == 0.9


class _FakeFilesAPI:
    def __init__(self) -> None:
        self.count = 0

    def upload(self, file: tuple[str, bytes, str]) -> SimpleNamespace:
        self.count += 1
        return SimpleNamespace(id=f"file-{self.count}-{file[0]}")


def test_prepare_files_api_uploads_registers_run_local_file_ids(tmp_path: Path) -> None:
    layout = ProjectLayout(
        series_root=tmp_path / "series" / book_acceptance.SERIES_ID,
        book_id=book_acceptance.BOOK_ID,
    )
    data_root = tmp_path / "run-data"
    managed_config = ManagedAgentConfig(files_api_enabled=True)
    fake_anthropic = SimpleNamespace(beta=SimpleNamespace(files=_FakeFilesAPI()))
    client = FilesAPIClient(data_root=data_root, client=fake_anthropic)

    uploaded = book_acceptance.prepare_files_api_uploads(
        layout=layout,
        series_id=book_acceptance.SERIES_ID,
        data_root=data_root,
        managed_config=managed_config,
        client=client,
    )

    assert uploaded["series_bible"].startswith("file-1-")
    assert uploaded["voice_profile"].startswith("file-2-")
    assert "char_emma_chen" in uploaded
    assert managed_config.get_file_id("series_bible") == uploaded["series_bible"]
    saved_path = data_root / book_acceptance.SERIES_ID / "file_ids.json"
    assert json.loads(saved_path.read_text(encoding="utf-8")) == uploaded
