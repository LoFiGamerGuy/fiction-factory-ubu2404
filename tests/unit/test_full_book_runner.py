"""Tests for the unattended production full-book runner."""

from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
from pipeline.job_runner import SceneRunResult

full_book = importlib.import_module("scripts.run_full_book")


class FakeJobRunner:
    """No-API scene runner that writes deterministic final scene files."""

    def __init__(self, ctx: AgentContext) -> None:
        self.ctx = ctx
        self.scene_ids: list[str] = []
        self.word_count_targets: list[int] = []

    def run_scene(self, job_context: JobContext) -> SceneRunResult:
        self.scene_ids.append(job_context.scene_id)
        self.word_count_targets.append(job_context.word_count_target)
        text = " ".join(
            f"{job_context.scene_id}_word_{index}" for index in range(job_context.word_count_target)
        )
        output_path = self.ctx.project_layout.scene_output_path(
            job_context.chapter_id,
            job_context.scene_id,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        return SceneRunResult(
            scene_id=job_context.scene_id,
            job_id=job_context.job_id,
            thread_id=job_context.job_id,
            final_text=text,
            force_resolved=False,
            convergence_decision="GO",
            revise_count=0,
            error="",
            final_state={
                "job_id": job_context.job_id,
                "scene_id": job_context.scene_id,
                "book_id": job_context.book_id,
                "series_id": job_context.series_id,
                "chapter_id": job_context.chapter_id,
                "model_tier": job_context.model_tier,
                "seed": job_context.seed,
                "scene_brief": job_context.scene_brief,
                "word_count_target": job_context.word_count_target,
                "heat_level": job_context.heat_level,
                "writer_output": {},
                "editor_output": {"edited_text": text},
                "quality_output": {},
                "final_text": text,
                "convergence_decision": "GO",
                "revise_count": 0,
                "force_resolved": False,
                "force_resolve_reason": "",
                "bible_contradiction": False,
                "overdue_promises": [],
                "error": "",
            },
        )


def _write_cedar_fixture(tmp_path: Path) -> tuple[Path, Path]:
    source = full_book.WORKSPACE_ROOT / "data" / "series" / "cedar-harbor-romance"
    series_root_base = tmp_path / "series"
    target = series_root_base / "cedar-harbor-romance"
    (target / "data" / "books" / "book01").mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "spec.yaml", target / "spec.yaml")
    shutil.copy2(
        source / "data" / "books" / "book01" / "spec.yaml",
        target / "data" / "books" / "book01" / "spec.yaml",
    )
    shutil.copy2(
        source / "data" / "books" / "book01" / "scene_inventory.json",
        target / "data" / "books" / "book01" / "scene_inventory.json",
    )
    config_path = tmp_path / "pipeline_config.json"
    config_path.write_text(
        json.dumps(
            {
                "series_root": str(series_root_base),
                "series_id": "cedar-harbor-romance",
                "book_id": "book01",
                "model_router_path": str(full_book.WORKSPACE_ROOT / "model_router.json"),
                "model_tier": "test",
                "llm_provider": "openai",
                "output_dir": str(tmp_path / "output"),
                "data_root": str(tmp_path / "ledgers"),
                "workspace_root": str(full_book.WORKSPACE_ROOT),
                "max_revisions": 1,
                "seed": 1842,
            }
        ),
        encoding="utf-8",
    )
    return config_path, target


def _factory(instances: list[FakeJobRunner]) -> Any:
    def make(ctx: AgentContext) -> FakeJobRunner:
        runner = FakeJobRunner(ctx)
        instances.append(runner)
        return runner

    return make


def _inventory_scene_ids(series_root: Path) -> list[str]:
    raw = json.loads(
        (series_root / "data" / "books" / "book01" / "scene_inventory.json").read_text(
            encoding="utf-8"
        )
    )
    return [str(scene["scene_id"]) for scene in raw["scenes"]]


def test_full_book_runner_executes_cedar_inventory_in_order(tmp_path: Path) -> None:
    config_path, series_root = _write_cedar_fixture(tmp_path)
    instances: list[FakeJobRunner] = []

    payload = full_book.run_full_book(
        config_path=config_path,
        run_id="cedar-full-order",
        run_corpus_eval=False,
        run_dashboard_checks=False,
        job_runner_factory=_factory(instances),
    )

    expected_scene_ids = _inventory_scene_ids(series_root)
    assert instances[0].scene_ids == expected_scene_ids
    assert payload["run_passed"] is True
    assert payload["planned_scene_count"] == 50
    assert payload["inventory_total_scene_count"] == 50
    assert payload["run_scene_count"] == 50
    assert payload["partial_run"] is False
    assert payload["verifier_status"]["passed"] is True
    assert Path(payload["summary_path"]).exists()
    assert Path(payload["manuscript_path"]).exists()


def test_full_book_runner_max_scenes_truncates_inventory(tmp_path: Path) -> None:
    config_path, series_root = _write_cedar_fixture(tmp_path)
    instances: list[FakeJobRunner] = []

    payload = full_book.run_full_book(
        config_path=config_path,
        run_id="cedar-max-scenes",
        max_scenes=3,
        run_corpus_eval=False,
        run_dashboard_checks=False,
        job_runner_factory=_factory(instances),
    )

    assert instances[0].scene_ids == _inventory_scene_ids(series_root)[:3]
    assert payload["run_passed"] is True
    assert payload["planned_scene_count"] == 3
    assert payload["inventory_total_scene_count"] == 50
    assert payload["partial_run"] is True
    assert payload["verifier_status"]["skipped"] is True
    assert payload["verifier_status"]["reason"] == "partial_run"


def test_full_book_runner_resume_skips_completed_scenes(tmp_path: Path) -> None:
    config_path, _series_root = _write_cedar_fixture(tmp_path)
    first_instances: list[FakeJobRunner] = []
    second_instances: list[FakeJobRunner] = []

    first_payload = full_book.run_full_book(
        config_path=config_path,
        run_id="cedar-resume",
        max_scenes=2,
        run_corpus_eval=False,
        run_dashboard_checks=False,
        job_runner_factory=_factory(first_instances),
    )
    second_payload = full_book.run_full_book(
        config_path=config_path,
        run_id="cedar-resume",
        max_scenes=2,
        run_corpus_eval=False,
        run_dashboard_checks=False,
        job_runner_factory=_factory(second_instances),
    )

    assert first_instances[0].scene_ids == ["ch01_sc01", "ch01_sc02"]
    assert first_payload["skipped_scenes"] == 0
    assert second_instances[0].scene_ids == []
    assert second_payload["skipped_scenes"] == 2
    assert [scene["status"] for scene in second_payload["scenes"]] == ["skipped", "skipped"]


def test_full_book_runner_force_reruns_selected_scenes(tmp_path: Path) -> None:
    config_path, _series_root = _write_cedar_fixture(tmp_path)
    first_instances: list[FakeJobRunner] = []
    force_instances: list[FakeJobRunner] = []

    full_book.run_full_book(
        config_path=config_path,
        run_id="cedar-force",
        max_scenes=2,
        run_corpus_eval=False,
        run_dashboard_checks=False,
        job_runner_factory=_factory(first_instances),
    )
    payload = full_book.run_full_book(
        config_path=config_path,
        run_id="cedar-force",
        max_scenes=2,
        force=True,
        run_corpus_eval=False,
        run_dashboard_checks=False,
        job_runner_factory=_factory(force_instances),
    )

    assert force_instances[0].scene_ids == ["ch01_sc01", "ch01_sc02"]
    assert payload["skipped_scenes"] == 0
    status_lines = Path(payload["status_path"]).read_text(encoding="utf-8").splitlines()
    assert len(status_lines) == 2
    assert all(json.loads(line)["status"] == "completed" for line in status_lines)


def test_full_book_runner_summary_contains_unattended_contract(tmp_path: Path) -> None:
    config_path, _series_root = _write_cedar_fixture(tmp_path)
    instances: list[FakeJobRunner] = []

    payload = full_book.run_full_book(
        config_path=config_path,
        run_id="cedar-summary",
        max_scenes=1,
        run_corpus_eval=False,
        run_dashboard_checks=True,
        job_runner_factory=_factory(instances),
    )
    saved = json.loads(Path(payload["summary_path"]).read_text(encoding="utf-8"))

    assert saved["run_type"] == "production_full_book"
    assert saved["run_id"] == "cedar-summary"
    assert saved["provider"] == "openai"
    assert saved["model_tier"] == "test"
    assert saved["max_scenes"] == 1
    assert saved["resume_enabled"] is True
    assert saved["force_rerun"] is False
    assert saved["router_config_path"].endswith("model_router.run.json")
    assert saved["dashboard_api_status"]["passed"] is True
    assert saved["run_passed"] is True
    assert (
        json.loads((full_book.WORKSPACE_ROOT / "model_router.json").read_text())["model_tier"]
        == "test"
    )


def test_eval_status_uses_selected_inventory_paths(monkeypatch: Any, tmp_path: Path) -> None:
    scene_dir = tmp_path / "scenes"
    selected = [scene_dir / "ch01_sc01.md", scene_dir / "ch01_sc02.md"]
    stale = scene_dir / "ch25_sc02.md"
    for path in [*selected, stale]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Clean concrete prose. " * 100, encoding="utf-8")

    captured: dict[str, list[Path]] = {}

    def fake_evaluate_scenes(**kwargs: Any) -> Any:
        paths = list(kwargs["scene_paths"])
        captured["scene_paths"] = paths
        return SimpleNamespace(
            passed=True,
            scene_count=len(paths),
            runs=[
                SimpleNamespace(
                    scene_path=path,
                    passed=True,
                    voice=SimpleNamespace(score=0.9),
                    ai_tell=SimpleNamespace(score=0.9),
                )
                for path in paths
            ],
        )

    monkeypatch.setattr(full_book.run_eval, "evaluate_scenes", fake_evaluate_scenes)

    status = full_book.build_eval_status(
        scene_paths=selected,
        model_tier="test",
        required_scene_count=2,
        voice_threshold=0.75,
        ai_tell_threshold=0.5,
    )

    assert captured["scene_paths"] == selected
    assert status["scene_count"] == 2
    assert stale not in [Path(item["scene_path"]) for item in status["scenes"]]
