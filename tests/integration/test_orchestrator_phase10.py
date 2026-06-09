"""Phase 10 CLI integration: validate-spec -> init-book -> job -> verify-book."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from pipeline.agents.agent_models import EditorOutput, QualityResult, WriterOutput
from pipeline.core.job_context import JobContext
from pipeline.orchestrator import main


def _write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "pipeline_config.json"
    config_path.write_text(
        json.dumps(
            {
                "series_root": str(tmp_path / "series"),
                "series_id": "series_test",
                "book_id": "book01",
                "model_router_path": str(Path("model_router.json")),
                "output_dir": str(tmp_path / "output"),
                "data_root": str(tmp_path / "ledger_data"),
                "max_revisions": 1,
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _write_specs(tmp_path: Path) -> Path:
    series_dir = tmp_path / "series" / "series_test"
    book_dir = series_dir / "data" / "books" / "book01"
    book_dir.mkdir(parents=True, exist_ok=True)
    series_spec = {
        "series_id": "series_test",
        "genre_config": {
            "genre_name": "romance",
            "heat_curve": "flat",
            "word_count_target": 12,
            "chapter_count": 1,
            "scene_function_vocabulary": ["resolution"],
            "required_scene_slots": ["HEA_or_HFN"],
            "hea_required": True,
        },
    }
    book_spec = {"chapter_count": 1, "scenes_per_chapter": 1, "word_count_target": 12}
    series_spec_path = series_dir / "spec.yaml"
    series_spec_path.write_text(yaml.dump(series_spec), encoding="utf-8")
    (book_dir / "spec.yaml").write_text(yaml.dump(book_spec), encoding="utf-8")
    return series_spec_path


def _patch_cli_agents(monkeypatch: Any) -> None:
    class FakeWriter:
        def __init__(self, ctx: object, model_router: object) -> None:
            pass

        def run(self, jc: JobContext) -> JobContext:
            output = WriterOutput(
                draft_text="one two three four five six seven eight nine ten eleven twelve",
                word_count=12,
                scene_id=jc.scene_id,
            )
            return jc.with_output("writer_agent", output.model_dump())

    class FakeEditor:
        def __init__(self, ctx: object, model_router: object) -> None:
            pass

        def run(self, jc: JobContext) -> JobContext:
            output = EditorOutput(
                edited_text="one two three four five six seven eight nine ten eleven twelve"
            )
            return jc.with_output("editor_agent", output.model_dump())

    class FakeContinuity:
        def __init__(self, **kwargs: object) -> None:
            pass

        def run(self, jc: JobContext) -> JobContext:
            return jc

        def commit_approved_changes(self, jc: JobContext) -> None:
            return None

    class FakeSeriesArcTracker:
        def __init__(self, ledger: object) -> None:
            pass

        def apply_approved_updates(self, jc: JobContext) -> None:
            return None

    class FakeQuality:
        def __init__(self, ctx: object) -> None:
            pass

        def run(self, jc: JobContext) -> JobContext:
            output = QualityResult(needs_review=False, tier="pass", scene_id=jc.scene_id)
            return jc.with_output("quality_agent", output.model_dump())

        def update_ledgers(self, jc: JobContext) -> None:
            return None

    monkeypatch.setattr("pipeline.job_runner.WriterAgent", FakeWriter)
    monkeypatch.setattr("pipeline.agents.editor_agent.EditorAgent", FakeEditor)
    monkeypatch.setattr("pipeline.job_runner.ContinuityAgent", FakeContinuity)
    monkeypatch.setattr("pipeline.job_runner.SeriesArcTracker", FakeSeriesArcTracker)
    monkeypatch.setattr("pipeline.job_runner.QualityAgent", FakeQuality)


def test_phase10_cli_validate_init_job_verify(tmp_path: Path, monkeypatch: Any) -> None:
    config_path = _write_config(tmp_path)
    series_spec_path = _write_specs(tmp_path)
    _patch_cli_agents(monkeypatch)

    assert main(["--validate-spec", str(series_spec_path), "--config", str(config_path)]) == 0
    assert main(["--init-book", "series_test", "1", "--config", str(config_path)]) == 0
    assert main(["--job", "ch01_sc01", "--config", str(config_path)]) == 0
    assert main(["--verify-book", "book01", "--config", str(config_path)]) == 0


def test_verify_book_fails_missing_heat_curve(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    series_spec_path = _write_specs(tmp_path)
    raw_spec = yaml.safe_load(series_spec_path.read_text(encoding="utf-8"))
    raw_spec["genre_config"].pop("heat_curve")
    series_spec_path.write_text(yaml.dump(raw_spec), encoding="utf-8")

    assert main(["--init-book", "series_test", "1", "--config", str(config_path)]) == 0
    assert main(["--verify-book", "book01", "--config", str(config_path)]) == 1


def test_resume_requires_scene_id(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    assert main(["--resume", "thread-1", "--config", str(config_path)]) == 1
