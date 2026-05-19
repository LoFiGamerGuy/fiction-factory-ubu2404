"""3-scene integration test (T14.7) — no LLM calls, focuses on planner/verifier/ledger wiring."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline.book_structural_verifier import BookOutput, BookStructuralVerifier
from pipeline.book_structure_planner import BookStructurePlanner
from pipeline.ledgers.ledger_manager import LedgerManager, SceneResult
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)

_ROMANCE_SERIES_SPEC: dict[str, Any] = {
    "series_id": "fixture-series",
    "genre_config": {
        "genre_name": "romance",
        "heat_curve": "rising",
        "word_count_target": 12000,
        "chapter_count": 12,
        "scene_function_vocabulary": ["meet_cute", "escalation", "resolution"],
        "required_scene_slots": ["meet_cute"],
        "hea_required": False,
    },
}

_BOOK_SPEC: dict[str, Any] = {
    "chapter_count": 12,
    "scenes_per_chapter": 1,
    "word_count_target": 12000,
}


def _make_spec(tmp_path: Path) -> ProjectSpec:
    return ProjectSpec(
        book_id="book01",
        series_id="fixture-series",
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(
            genre_name="romance", word_count_min=5000, word_count_max=15000
        ),
        sensitivity_thresholds=ResolvedSensitivityThresholds(),
        goal_weights=ResolvedGoalWeights(),
        audience_expectations=ResolvedAudienceExpectations(),
    )


class TestBookStructurePlannerCreatesInventory:
    def test_12scene_inventory_written(self, tmp_path: Path) -> None:
        planner = BookStructurePlanner()
        inv = planner.plan(
            book_id="book01",
            series_id="fixture-series",
            series_spec=_ROMANCE_SERIES_SPEC,
            book_spec=_BOOK_SPEC,
            book_dir=tmp_path / "book01",
        )
        assert inv.total_scenes == 12
        assert len(inv.scenes) == 12
        assert (tmp_path / "book01" / "scene_inventory.json").exists()

    def test_scene_ids_correct(self, tmp_path: Path) -> None:
        planner = BookStructurePlanner()
        inv = planner.plan(
            book_id="book01",
            series_id="fixture-series",
            series_spec=_ROMANCE_SERIES_SPEC,
            book_spec=_BOOK_SPEC,
            book_dir=tmp_path / "book01",
        )
        assert inv.scenes[0].scene_id == "ch01_sc01"
        assert inv.scenes[-1].scene_id == "ch12_sc01"


class TestBookStructuralVerifierPassesClean:
    def test_clean_book_passes(self, tmp_path: Path) -> None:
        planner = BookStructurePlanner()
        inv = planner.plan(
            book_id="book01",
            series_id="fixture-series",
            series_spec=_ROMANCE_SERIES_SPEC,
            book_spec=_BOOK_SPEC,
            book_dir=tmp_path / "book01",
        )
        book_output = BookOutput(
            book_id="book01",
            actual_word_count=12000,
            scenes_completed=[
                {
                    "scene_id": s.scene_id,
                    "chapter": s.chapter,
                    "heat_level": s.heat_level_target,
                    "scene_function": s.scene_function,
                }
                for s in inv.scenes
            ],
        )
        spec = _make_spec(tmp_path)
        verifier = BookStructuralVerifier()
        report = verifier.verify(book_output, spec, inv, _ROMANCE_SERIES_SPEC["genre_config"])
        assert report.passed, [f.description for f in report.failed_checks]


class TestLedgerManagerTracksScenes:
    def test_ledger_update_no_error(self, tmp_path: Path) -> None:
        mgr = LedgerManager(book_id="book01", series_id="fixture-series", data_root=tmp_path)
        scene_result = SceneResult(
            scene_id="ch01_sc01",
            book_id="book01",
            chapter_id="1",
            timestamp=datetime.now(UTC).isoformat(),
            scene_type="action",
        )
        # update() should not raise even with empty events
        mgr.update(scene_result)

    def test_ledger_dashboard_summary(self, tmp_path: Path) -> None:
        mgr = LedgerManager(book_id="book01", series_id="fixture-series", data_root=tmp_path)
        dash = mgr.get_dashboard_summary("book01", "ch01_sc01")
        assert dash.book_id == "book01"


class TestSpecValidatorIntegration:
    def test_valid_spec_passes(self, tmp_path: Path) -> None:
        from pipeline.spec_validator_agent import SpecValidatorAgent

        spec_path = tmp_path / "spec.yaml"
        spec_path.write_text(
            "series_id: fixture-series\ngenre_config:\n  genre_name: romance\n",
            encoding="utf-8",
        )
        agent = SpecValidatorAgent()
        result = agent.validate(spec_path)
        assert result.valid, result.errors

    def test_invalid_spec_fails(self, tmp_path: Path) -> None:
        from pipeline.spec_validator_agent import SpecValidatorAgent

        spec_path = tmp_path / "spec.yaml"
        spec_path.write_text("genre_config:\n  genre_name: romance\n", encoding="utf-8")
        agent = SpecValidatorAgent()
        result = agent.validate(spec_path)
        assert not result.valid


class TestFullPipelineFlowNoLLM:
    def test_3scene_flow_under_5s(self, tmp_path: Path) -> None:
        start = time.monotonic()

        # 1. Plan
        planner = BookStructurePlanner()
        inv = planner.plan(
            book_id="book01",
            series_id="fixture-series",
            series_spec=_ROMANCE_SERIES_SPEC,
            book_spec=_BOOK_SPEC,
            book_dir=tmp_path / "book01",
        )
        assert inv.total_scenes == 12

        # 2. Ledger updates for each scene
        mgr = LedgerManager(book_id="book01", series_id="fixture-series", data_root=tmp_path)
        for slot in inv.scenes:
            mgr.update(
                SceneResult(
                    scene_id=slot.scene_id,
                    book_id="book01",
                    chapter_id=str(slot.chapter),
                    timestamp=datetime.now(UTC).isoformat(),
                    scene_type="action",
                )
            )

        # 3. Verify book
        book_output = BookOutput(
            book_id="book01",
            actual_word_count=12000,
            scenes_completed=[
                {
                    "scene_id": s.scene_id,
                    "chapter": s.chapter,
                    "heat_level": s.heat_level_target,
                    "scene_function": s.scene_function,
                }
                for s in inv.scenes
            ],
        )
        spec = _make_spec(tmp_path)
        report = BookStructuralVerifier().verify(
            book_output, spec, inv, _ROMANCE_SERIES_SPEC["genre_config"]
        )
        assert report.passed, [f.description for f in report.failed_checks]

        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"Pipeline flow took {elapsed:.2f}s (limit: 5s)"
