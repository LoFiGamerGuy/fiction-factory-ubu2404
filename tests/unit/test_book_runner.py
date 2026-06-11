"""Tests for ordered book-level execution over JobRunner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.book_runner import BookRunner, BookScene, scenes_from_inventory
from pipeline.book_structure_planner import SceneInventory, SceneSlot
from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
from pipeline.core.project_layout import ProjectLayout
from pipeline.job_runner import SceneRunResult
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)
from pipeline.profiles.spec_loader import SpecLoader


def _spec() -> ProjectSpec:
    return ProjectSpec(
        book_id="book-runner-test-book",
        series_id="book-runner-test-series",
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(
            genre_name="romance", word_count_min=1, word_count_max=5000
        ),
        sensitivity_thresholds=ResolvedSensitivityThresholds(),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )


def _ctx(tmp_path: Path) -> AgentContext:
    layout = ProjectLayout(series_root=tmp_path / "series", book_id="book-runner-test-book")
    return AgentContext(
        project_layout=layout,
        spec_loader=SpecLoader(workspace_root=tmp_path),
        ledger_manager=LedgerManager(
            book_id="book-runner-test-book",
            series_id="book-runner-test-series",
            data_root=tmp_path / "ledgers",
        ),
        log_path=tmp_path / "agent.log",
        output_dir=tmp_path / "output",
        model_tier="test",
    )


def _scenes() -> tuple[BookScene, ...]:
    return (
        BookScene(
            scene_id="ch01_sc01",
            chapter_id=1,
            scene_brief="Meet cute.",
            word_count_target=120,
            heat_level=1,
        ),
        BookScene(
            scene_id="ch01_sc02",
            chapter_id=1,
            scene_brief="Forced collaboration.",
            word_count_target=120,
            heat_level=1,
        ),
        BookScene(
            scene_id="ch02_sc01",
            chapter_id=2,
            scene_brief="First conflict.",
            word_count_target=120,
            heat_level=2,
        ),
    )


class FakeJobRunner:
    def __init__(self, ctx: AgentContext, *, fail_on: str | None = None) -> None:
        self.ctx = ctx
        self.fail_on = fail_on
        self.scene_ids: list[str] = []
        self.seeds: list[int] = []

    def run_scene(self, job_context: JobContext) -> SceneRunResult:
        self.scene_ids.append(job_context.scene_id)
        self.seeds.append(job_context.seed)
        if job_context.scene_id == self.fail_on:
            raise RuntimeError(f"boom: {job_context.scene_id}")

        text = f'{job_context.scene_id}: "We choose the next step," Emma said to Marcus.'
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
                "convergence_decision": "GO",
                "revise_count": 0,
                "final_text": text,
                "force_resolved": False,
                "force_resolve_reason": "",
                "bible_contradiction": False,
                "overdue_promises": [],
                "error": "",
            },
        )


def test_book_runner_executes_scenes_in_order_and_records_status(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    fake_runner = FakeJobRunner(ctx)
    runner = BookRunner(agent_ctx=ctx, job_runner=fake_runner)

    result = runner.run_book(run_id="book-run", spec=_spec(), scenes=_scenes(), base_seed=100)

    assert result.passed
    assert result.planned_scene_count == 3
    assert result.attempted_scene_count == 3
    assert result.successful_scenes == 3
    assert result.go_scenes == 3
    assert fake_runner.scene_ids == ["ch01_sc01", "ch01_sc02", "ch02_sc01"]
    assert fake_runner.seeds == [101, 102, 103]

    status_lines = [json.loads(line) for line in Path(result.status_path).read_text().splitlines()]
    assert [line["scene_id"] for line in status_lines] == fake_runner.scene_ids
    assert all(line["status"] == "completed" for line in status_lines)
    assert all(line["convergence_decision"] == "GO" for line in status_lines)
    assert all(line["word_count"] > 0 for line in status_lines)
    assert all(Path(line["output_path"]).exists() for line in status_lines)


def test_book_runner_records_error_and_stops_by_default(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    fake_runner = FakeJobRunner(ctx, fail_on="ch01_sc02")
    runner = BookRunner(agent_ctx=ctx, job_runner=fake_runner)

    result = runner.run_book(run_id="book-run", spec=_spec(), scenes=_scenes())

    assert not result.passed
    assert result.planned_scene_count == 3
    assert result.attempted_scene_count == 2
    assert result.successful_scenes == 1
    assert result.failed_scenes == 1
    assert fake_runner.scene_ids == ["ch01_sc01", "ch01_sc02"]

    status_lines = [json.loads(line) for line in Path(result.status_path).read_text().splitlines()]
    assert [line["status"] for line in status_lines] == ["completed", "error"]
    assert "boom: ch01_sc02" in status_lines[-1]["error"]


def test_assemble_manuscript_orders_scene_files_and_writes_summary(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    fake_runner = FakeJobRunner(ctx)
    runner = BookRunner(agent_ctx=ctx, job_runner=fake_runner)
    result = runner.run_book(run_id="book-run", spec=_spec(), scenes=_scenes())

    ordered_scenes = (_scenes()[1], _scenes()[0], _scenes()[2])
    manuscript = runner.assemble_manuscript(ordered_scenes)
    text = Path(manuscript.manuscript_path).read_text(encoding="utf-8")

    assert text.startswith("# book-runner-test-book\n")
    assert "## Chapter 1" in text
    assert "## Chapter 2" in text
    assert text.index("### Scene ch01_sc02") < text.index("### Scene ch01_sc01")
    assert manuscript.scene_count == 3
    assert manuscript.word_count == sum(scene.word_count for scene in result.scenes)
    cost_log = tmp_path / "cost_log.jsonl"
    cost_log.write_text(
        json.dumps(
            {
                "input_tokens": 100,
                "output_tokens": 25,
                "total_tokens": 125,
                "cost_usd": 0.0001,
            }
        )
        + "\n"
        + json.dumps(
            {
                "input_tokens": 200,
                "output_tokens": 50,
                "cost_usd": 0.0002,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = runner.write_book_run_summary(
        result=result,
        provider="fake",
        manuscript=manuscript,
        eval_status={"passed": True},
        verifier_status={"passed": True},
        draft_acceptance_status={"passed": True, "classification": "draft_within_target"},
        cost_log_path=cost_log,
    )
    summary_path = Path(payload["summary_path"])
    saved = json.loads(summary_path.read_text(encoding="utf-8"))

    assert saved["provider"] == "fake"
    assert saved["manuscript_path"] == manuscript.manuscript_path
    assert saved["total_word_count"] == manuscript.word_count
    assert saved["go_scenes"] == 3
    assert saved["failed_scene_ids"] == []
    assert saved["eval_status"] == {"passed": True}
    assert saved["verifier_status"] == {"passed": True}
    assert saved["draft_acceptance_status"] == {
        "passed": True,
        "classification": "draft_within_target",
    }
    assert saved["ledger_dashboard_summary"]["book_id"] == "book-runner-test-book"
    assert saved["checkpoint_thread_ids"]["ch01_sc01"] == "book-run_ch01_sc01"
    assert saved["cost_summary"]["entry_count"] == 2
    assert saved["cost_summary"]["input_tokens"] == 300
    assert saved["cost_summary"]["output_tokens"] == 75
    assert saved["cost_summary"]["total_tokens"] == 375
    assert saved["cost_summary"]["cost_usd"] == 0.0003
    assert saved["files_api"] == {"enabled": False, "uploaded_file_ids": {}}


def test_assemble_manuscript_missing_scene_fails_clearly(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    runner = BookRunner(agent_ctx=ctx, job_runner=FakeJobRunner(ctx))

    with pytest.raises(FileNotFoundError, match="Missing finalized scene file for ch01_sc01"):
        runner.assemble_manuscript(_scenes())


def test_resume_skips_completed_scene_reruns_failed_then_force_regenerates_all(
    tmp_path: Path,
) -> None:
    ctx = _ctx(tmp_path)
    spec = _spec()
    scenes = _scenes()
    first_fake = FakeJobRunner(ctx, fail_on="ch01_sc02")
    first_runner = BookRunner(agent_ctx=ctx, job_runner=first_fake)

    first_result = first_runner.run_book(run_id="book-run", spec=spec, scenes=scenes)

    assert not first_result.passed
    assert first_fake.scene_ids == ["ch01_sc01", "ch01_sc02"]

    resume_fake = FakeJobRunner(ctx)
    resume_runner = BookRunner(agent_ctx=ctx, job_runner=resume_fake)
    resume_result = resume_runner.run_book(run_id="book-run-resume", spec=spec, scenes=scenes)

    assert resume_result.passed
    assert resume_result.skipped_scenes == 1
    assert resume_result.previous_failed_scene_ids == ["ch01_sc02"]
    assert resume_fake.scene_ids == ["ch01_sc02", "ch02_sc01"]
    assert [record.status for record in resume_result.scenes] == [
        "skipped",
        "completed",
        "completed",
    ]
    manuscript = resume_runner.assemble_manuscript(scenes)
    payload = resume_runner.write_book_run_summary(
        result=resume_result,
        provider="fake",
        manuscript=manuscript,
    )
    assert payload["previous_failed_scene_ids"] == ["ch01_sc02"]
    assert payload["checkpoint_thread_ids"]["ch01_sc01"] == "book-run_ch01_sc01"
    assert payload["failed_scene_ids"] == []

    force_fake = FakeJobRunner(ctx)
    force_runner = BookRunner(agent_ctx=ctx, job_runner=force_fake)
    force_result = force_runner.run_book(
        run_id="book-run-force",
        spec=spec,
        scenes=scenes,
        force=True,
    )

    assert force_result.passed
    assert force_result.skipped_scenes == 0
    assert force_result.previous_failed_scene_ids == []
    assert force_fake.scene_ids == ["ch01_sc01", "ch01_sc02", "ch02_sc01"]
    status_lines = [
        json.loads(line) for line in Path(force_result.status_path).read_text().splitlines()
    ]
    assert len(status_lines) == 3
    assert all(line["status"] == "completed" for line in status_lines)


def test_scenes_from_inventory_preserves_inventory_order_and_overrides_briefs() -> None:
    inventory = SceneInventory(
        book_id="book-runner-test-book",
        series_id="book-runner-test-series",
        total_scenes=2,
        word_count_target=240,
        scenes=[
            SceneSlot(
                scene_id="ch01_sc01",
                chapter=1,
                act=1,
                scene_number=1,
                word_count_target=120,
                scene_function="meet_cute",
                heat_level_target=1,
                position=0.0,
            ),
            SceneSlot(
                scene_id="ch01_sc02",
                chapter=1,
                act=1,
                scene_number=2,
                word_count_target=120,
                scene_function="forced_proximity",
                heat_level_target=1,
                position=1.0,
            ),
        ],
    )

    scenes = scenes_from_inventory(inventory, scene_briefs={"ch01_sc02": "Custom brief."})

    assert [scene.scene_id for scene in scenes] == ["ch01_sc01", "ch01_sc02"]
    assert scenes[0].scene_brief == "Write meet_cute for ch01_sc01 in chapter 1."
    assert scenes[1].scene_brief == "Custom brief."
