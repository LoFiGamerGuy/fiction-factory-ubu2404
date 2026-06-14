#!/usr/bin/env python3
"""Book acceptance runner for repeatable full-book generation.

Runs Romance Module fixtures through ``BookRunner`` and the same ``JobRunner``
scene path used by Phase 14 acceptance. The default tier is test; production
comparisons must pass ``--model-tier production`` explicitly and still use the
run-local router config written by this script.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# ruff: noqa: E402
from pipeline.book_runner import BookRunner, BookScene
from pipeline.book_structural_verifier import BookOutput, BookStructuralVerifier
from pipeline.book_structure_planner import SceneInventory, SceneSlot
from pipeline.core.agent_context import AgentContext
from pipeline.core.managed_agent_config import ManagedAgentConfig
from pipeline.core.model_router import ModelRouter
from pipeline.core.project_layout import ProjectLayout
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.memory.files_api_client import FilesAPIClient
from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)
from pipeline.profiles.spec_loader import SpecLoader
from scripts import run_eval

logger = logging.getLogger(__name__)

BOOK_ID = "book-acceptance-romance-01"
NOVELLA_BOOK_ID = "book-acceptance-romance-novella-01"
SERIES_ID = "book-acceptance-series"
SHORT_BOOK_WORD_COUNT_TARGET = 3300
NOVELLA_WORD_COUNT_TARGET = 4600
FixtureName = Literal["short", "novella"]
AcceptanceMode = Literal["draft", "final"]
DEFAULT_DRAFT_SURPLUS_ALLOWED_PCT = 0.25

DEFAULT_SCENES: tuple[BookScene, ...] = (
    BookScene(
        scene_id="ch01_sc01_meet_cute",
        chapter_id=1,
        scene_brief=(
            "Emma Chen, an architect trying to protect a waterfront renovation, meets "
            "Marcus Rivera, a chef defending his family cafe, when a storm strands them "
            "under the same torn awning. End with reluctant curiosity, not trust."
        ),
        word_count_target=450,
        heat_level=1,
        scene_function="meet_cute",
        act=1,
        scene_number=1,
    ),
    BookScene(
        scene_id="ch01_sc02_forced_collaboration",
        chapter_id=1,
        scene_brief=(
            "A permit crisis forces Emma and Marcus to inspect the cafe together. Their "
            "professional instincts clash, but each notices one specific competence in "
            "the other. End with a practical alliance."
        ),
        word_count_target=450,
        heat_level=1,
        scene_function="forced_proximity",
        act=1,
        scene_number=2,
    ),
    BookScene(
        scene_id="ch02_sc01_first_spark",
        chapter_id=2,
        scene_brief=(
            "During an after-hours repair, Emma and Marcus share a quiet, tactile moment "
            "over a broken tile mural. The attraction becomes undeniable, but both choose "
            "restraint because the project stakes are real."
        ),
        word_count_target=450,
        heat_level=2,
        scene_function="escalation",
        act=2,
        scene_number=1,
    ),
    BookScene(
        scene_id="ch02_sc02_first_date",
        chapter_id=2,
        scene_brief=(
            "Marcus cooks a staff-table dinner for Emma after closing. Their banter turns "
            "honest when Emma admits she is tired of buildings outlasting relationships. "
            "End with a near-kiss interrupted by bad news."
        ),
        word_count_target=450,
        heat_level=2,
        scene_function="first_date",
        act=2,
        scene_number=2,
    ),
    BookScene(
        scene_id="ch03_sc01_midpoint_intimacy",
        chapter_id=3,
        scene_brief=(
            "A public hearing goes unexpectedly well, and Emma and Marcus celebrate in the "
            "empty cafe kitchen. Let the intimacy advance through consent, humor, and "
            "specific sensory detail while keeping the heat at sensual."
        ),
        word_count_target=450,
        heat_level=3,
        scene_function="intimacy",
        act=2,
        scene_number=1,
    ),
    BookScene(
        scene_id="ch03_sc02_black_moment",
        chapter_id=3,
        scene_brief=(
            "Emma discovers Marcus withheld a letter that could change the renovation vote. "
            "Marcus believed he was protecting his family; Emma hears only another person "
            "deciding for her. End with a clean separation."
        ),
        word_count_target=450,
        heat_level=2,
        scene_function="black_moment",
        act=2,
        scene_number=2,
    ),
    BookScene(
        scene_id="ch04_sc01_grand_gesture",
        chapter_id=4,
        scene_brief=(
            "Marcus publicly backs Emma's revised design even though it costs him leverage. "
            "His gesture must be concrete, costly, and tied to what he learned about trust. "
            "Emma does not forgive him instantly, but she steps closer."
        ),
        word_count_target=450,
        heat_level=2,
        scene_function="grand_gesture",
        act=3,
        scene_number=1,
    ),
    BookScene(
        scene_id="ch04_sc02_hea_resolution",
        chapter_id=4,
        scene_brief=(
            "The cafe reopens with Emma's design and Marcus's family recipes intact. Resolve "
            "the central emotional wound with a specific promise for how they will build "
            "together. End with a clear HEA."
        ),
        word_count_target=450,
        heat_level=2,
        scene_function="resolution",
        act=3,
        scene_number=2,
        required_slot_id="HEA_or_HFN",
    ),
)

NOVELLA_SCENES: tuple[BookScene, ...] = (
    BookScene(
        scene_id="ch01_sc01_meet_cute",
        chapter_id=1,
        scene_brief=(
            "Emma Chen arrives before dawn to survey the endangered waterfront block and "
            "finds Marcus Rivera already unloading produce for the family cafe. Their first "
            "argument over access becomes a reluctant storm-shelter truce. End with curiosity."
        ),
        word_count_target=450,
        heat_level=1,
        scene_function="meet_cute",
        act=1,
        scene_number=1,
    ),
    BookScene(
        scene_id="ch01_sc02_public_stakes",
        chapter_id=1,
        scene_brief=(
            "At a neighborhood meeting, Emma presents a preservation-forward renovation plan "
            "while Marcus challenges every assumption that might hurt the cafe staff. Show the "
            "public stakes and each person's private vulnerability. End with forced collaboration."
        ),
        word_count_target=450,
        heat_level=1,
        scene_function="forced_proximity",
        act=1,
        scene_number=2,
    ),
    BookScene(
        scene_id="ch02_sc01_shared_history",
        chapter_id=2,
        scene_brief=(
            "Emma and Marcus inspect archived blueprints in city storage. A discovered photo ties "
            "Marcus's grandmother to the original pier design, complicating Emma's detached view "
            "of the project. End with a concrete shared research task."
        ),
        word_count_target=450,
        heat_level=1,
        scene_function="shared_history",
        act=1,
        scene_number=1,
    ),
    BookScene(
        scene_id="ch02_sc02_first_spark",
        chapter_id=2,
        scene_brief=(
            "A late-night leak in the cafe ceiling forces Emma and Marcus onto the same ladder. "
            "Let competence, humor, and specific touch create the first undeniable spark. Both "
            "step back because the professional stakes still matter."
        ),
        word_count_target=450,
        heat_level=2,
        scene_function="escalation",
        act=2,
        scene_number=2,
    ),
    BookScene(
        scene_id="ch03_sc01_first_date",
        chapter_id=3,
        scene_brief=(
            "Marcus cooks Emma a trial-menu dinner after closing so they can test a design idea "
            "with the staff tables reset. Their banter turns honest about ambition, family, and "
            "the fear of being the person who leaves. End with a near-kiss interrupted."
        ),
        word_count_target=450,
        heat_level=2,
        scene_function="first_date",
        act=2,
        scene_number=1,
    ),
    BookScene(
        scene_id="ch03_sc02_pressure_reveal",
        chapter_id=3,
        scene_brief=(
            "Emma learns the developer is using her firm's old drawings to pressure the city. "
            "Marcus sees her panic before she can hide it. Let him offer practical help instead "
            "of rescue, and let Emma accept one specific kindness."
        ),
        word_count_target=450,
        heat_level=2,
        scene_function="external_pressure",
        act=2,
        scene_number=2,
    ),
    BookScene(
        scene_id="ch04_sc01_midpoint_intimacy",
        chapter_id=4,
        scene_brief=(
            "After the revised design wins a temporary stay, Emma and Marcus celebrate in the "
            "empty cafe kitchen. Advance intimacy through consent, laughter, and sensory detail. "
            "End with both admitting this is no longer only about the project."
        ),
        word_count_target=450,
        heat_level=3,
        scene_function="intimacy",
        act=2,
        scene_number=1,
    ),
    BookScene(
        scene_id="ch04_sc02_family_complication",
        chapter_id=4,
        scene_brief=(
            "Marcus's sister warns Emma that Marcus confuses loyalty with control. Emma catches "
            "Marcus making a unilateral promise to protect the cafe, and the old wound lands "
            "hard. End with the first real emotional fracture."
        ),
        word_count_target=450,
        heat_level=2,
        scene_function="family_complication",
        act=2,
        scene_number=2,
    ),
    BookScene(
        scene_id="ch05_sc01_black_moment",
        chapter_id=5,
        scene_brief=(
            "Emma discovers Marcus withheld a city letter that could have changed the hearing. "
            "He meant protection; she hears betrayal and professional sabotage. Make the break "
            "clean, painful, and specific, with no instant forgiveness."
        ),
        word_count_target=450,
        heat_level=2,
        scene_function="black_moment",
        act=2,
        scene_number=1,
    ),
    BookScene(
        scene_id="ch05_sc02_repair_choice",
        chapter_id=5,
        scene_brief=(
            "Separated, Emma redesigns the final pitch around community ownership while Marcus "
            "tells his family the whole truth. Show each choosing repair without knowing whether "
            "romance will be restored. End with Marcus preparing a costly public stand."
        ),
        word_count_target=450,
        heat_level=1,
        scene_function="repair_choice",
        act=3,
        scene_number=2,
    ),
    BookScene(
        scene_id="ch06_sc01_grand_gesture",
        chapter_id=6,
        scene_brief=(
            "At the final hearing, Marcus publicly backs Emma's revised design even though it "
            "costs him leverage and exposes his mistake. The gesture must prove trust through "
            "action, not apology alone. Emma steps closer but keeps agency."
        ),
        word_count_target=450,
        heat_level=2,
        scene_function="grand_gesture",
        act=3,
        scene_number=1,
    ),
    BookScene(
        scene_id="ch06_sc02_hea_resolution",
        chapter_id=6,
        scene_brief=(
            "The cafe reopens in the preserved waterfront block. Resolve the project stakes and "
            "the emotional wound with a specific mutual promise about trust, work, and staying. "
            "End with a clear, earned HEA."
        ),
        word_count_target=450,
        heat_level=2,
        scene_function="resolution",
        act=3,
        scene_number=2,
        required_slot_id="HEA_or_HFN",
    ),
)


def get_fixture_scenes(fixture: FixtureName) -> tuple[BookScene, ...]:
    """Return ordered scenes for a named acceptance fixture."""
    if fixture == "short":
        return DEFAULT_SCENES
    if fixture == "novella":
        return NOVELLA_SCENES
    raise ValueError(f"Unknown fixture: {fixture}")


def get_fixture_book_id(fixture: FixtureName) -> str:
    """Return the generated book ID for a named acceptance fixture."""
    if fixture == "short":
        return BOOK_ID
    if fixture == "novella":
        return NOVELLA_BOOK_ID
    raise ValueError(f"Unknown fixture: {fixture}")


def get_fixture_word_count_target(fixture: FixtureName) -> int:
    """Return the verifier word-count target for a named acceptance fixture."""
    if fixture == "short":
        return SHORT_BOOK_WORD_COUNT_TARGET
    if fixture == "novella":
        return NOVELLA_WORD_COUNT_TARGET
    raise ValueError(f"Unknown fixture: {fixture}")


def create_fixture_spec(fixture: FixtureName = "short") -> ProjectSpec:
    """Create a compact Romance Module spec for an acceptance fixture."""
    scenes = get_fixture_scenes(fixture)
    word_target = get_fixture_word_count_target(fixture)
    return ProjectSpec(
        book_id=get_fixture_book_id(fixture),
        series_id=SERIES_ID,
        voice_axes=ResolvedVoiceAxes(
            internal_monologue_share=0.24,
            dialogue_to_narration_ratio=0.38,
        ),
        genre_config=ResolvedGenreConfig(
            genre_name="romance",
            genre_module_status="validated",
            scene_function_vocabulary=tuple(
                dict.fromkeys(scene.scene_function for scene in scenes)
            ),
            word_count_min=max(1, int(word_target * 0.7)),
            word_count_max=int(word_target * 1.3),
        ),
        sensitivity_thresholds=ResolvedSensitivityThresholds(max_heat_level=4.0),
        goal_weights=ResolvedGoalWeights(intent="kdp_commercial"),
        audience_expectations=ResolvedAudienceExpectations(reader_lens="romance_reader"),
    )


def create_short_book_spec() -> ProjectSpec:
    """Backward-compatible wrapper for the original short-book fixture spec."""
    return create_fixture_spec("short")


def create_fixture_inventory(fixture: FixtureName = "short") -> SceneInventory:
    """Create a SceneInventory matching a fixture's scene order."""
    scenes = get_fixture_scenes(fixture)
    total_scenes = len(scenes)
    return SceneInventory(
        book_id=get_fixture_book_id(fixture),
        series_id=SERIES_ID,
        total_scenes=total_scenes,
        word_count_target=get_fixture_word_count_target(fixture),
        scenes=[
            SceneSlot(
                scene_id=scene.scene_id,
                chapter=scene.chapter_id,
                act=scene.act,
                scene_number=scene.scene_number,
                word_count_target=scene.word_count_target,
                scene_function=scene.scene_function,
                heat_level_target=scene.heat_level,
                position=round(index / max(1, total_scenes - 1), 4),
                required_slot_id=scene.required_slot_id,
            )
            for index, scene in enumerate(scenes)
        ],
    )


def create_short_book_inventory() -> SceneInventory:
    """Backward-compatible wrapper for the original short-book inventory."""
    return create_fixture_inventory("short")


def create_fixture_genre_spec(fixture: FixtureName = "short") -> dict[str, Any]:
    """Genre verifier inputs matching a fixture's planned heat path."""
    scenes = get_fixture_scenes(fixture)
    total_scenes = len(scenes)
    return {
        "genre_name": "romance",
        "hea_required": True,
        "required_scene_slots": ["HEA_or_HFN"],
        "heat_curve_waypoints": [
            [round(index / max(1, total_scenes - 1), 4), scene.heat_level]
            for index, scene in enumerate(scenes)
        ],
    }


def create_short_book_genre_spec() -> dict[str, Any]:
    """Backward-compatible wrapper for the original short-book genre spec."""
    return create_fixture_genre_spec("short")


def build_verifier_status(
    result: Any,
    spec: ProjectSpec,
    fixture: FixtureName = "short",
) -> dict[str, Any]:
    """Run BookStructuralVerifier over a fixture output."""
    inventory = create_fixture_inventory(fixture)
    genre_spec = create_fixture_genre_spec(fixture)
    scene_by_id = {scene.scene_id: scene for scene in get_fixture_scenes(fixture)}
    scenes_completed = []
    for status in result.scenes:
        scene = scene_by_id[status.scene_id]
        scenes_completed.append(
            {
                "scene_id": status.scene_id,
                "chapter": status.chapter_id,
                "act": scene.act,
                "heat_level": scene.heat_level,
                "scene_function": scene.scene_function,
                "required_slot_id": scene.required_slot_id,
                "word_count": status.word_count,
            }
        )

    report = BookStructuralVerifier().verify(
        book_output=BookOutput(
            book_id=spec.book_id,
            actual_word_count=sum(status.word_count for status in result.scenes),
            scenes_completed=scenes_completed,
        ),
        spec=spec,
        inventory=inventory,
        genre_spec=genre_spec,
    )
    return {
        "passed": report.passed,
        "failed_checks": [
            {"check_name": check.check_name, "description": check.description}
            for check in report.failed_checks
        ],
    }


def build_eval_status(
    *,
    scene_dir: Path,
    model_tier: str,
    voice_threshold: float,
    ai_tell_threshold: float,
    required_scene_count: int = len(DEFAULT_SCENES),
) -> dict[str, Any]:
    """Run deterministic corpus eval and return compact JSON status."""
    scene_paths = run_eval._collect_scene_paths(scene_dir)
    suite = run_eval.evaluate_scenes(
        scene_paths=scene_paths,
        voice_threshold=voice_threshold,
        ai_tell_threshold=ai_tell_threshold,
        model_tier=model_tier,
        use_llm_voice=False,
        use_llm_ai_tell=False,
    )
    return {
        "passed": suite.passed and suite.scene_count >= required_scene_count,
        "scene_count": suite.scene_count,
        "required_scene_count": required_scene_count,
        "scenes": [
            {
                "scene_path": str(run.scene_path),
                "passed": run.passed,
                "voice_consistency": run.voice.score,
                "ai_tell": run.ai_tell.score,
            }
            for run in suite.runs
        ],
    }


def build_draft_acceptance_status(
    *,
    result: Any,
    target_word_count: int,
    actual_word_count: int,
    eval_status: Mapping[str, Any] | None,
    dashboard_api_status: Mapping[str, Any] | None = None,
    draft_surplus_allowed_pct: float = DEFAULT_DRAFT_SURPLUS_ALLOWED_PCT,
) -> dict[str, Any]:
    """Evaluate draft acceptance separately from final structural verification."""
    if draft_surplus_allowed_pct < 0:
        raise ValueError("draft_surplus_allowed_pct must be non-negative")

    surplus_words = max(0, actual_word_count - target_word_count)
    surplus_pct = round(surplus_words / target_word_count, 6) if target_word_count > 0 else 0.0
    draft_word_count_ceiling = target_word_count * (1 + draft_surplus_allowed_pct)
    within_draft_surplus = target_word_count > 0 and actual_word_count <= draft_word_count_ceiling
    all_scenes_complete = bool(result.passed)
    no_failed_scenes = int(result.failed_scenes) == 0
    no_force_resolved_scenes = int(result.force_resolved_scenes) == 0
    eval_passed = bool(eval_status is not None and eval_status.get("passed"))
    dashboard_api_passed = (
        None if dashboard_api_status is None else bool(dashboard_api_status.get("passed"))
    )
    dashboard_api_ok = dashboard_api_passed is not False
    passed = (
        all_scenes_complete
        and no_failed_scenes
        and no_force_resolved_scenes
        and eval_passed
        and dashboard_api_ok
        and within_draft_surplus
    )
    if not passed:
        classification = "draft_failed"
    elif surplus_words > 0:
        classification = "draft_surplus"
    else:
        classification = "draft_within_target"

    return {
        "passed": passed,
        "classification": classification,
        "all_scenes_complete": all_scenes_complete,
        "no_failed_scenes": no_failed_scenes,
        "no_force_resolved_scenes": no_force_resolved_scenes,
        "eval_passed": eval_passed,
        "dashboard_api_passed": dashboard_api_passed,
        "target_word_count": target_word_count,
        "actual_word_count": actual_word_count,
        "surplus_words": surplus_words,
        "surplus_pct": surplus_pct,
        "draft_surplus_allowed_pct": draft_surplus_allowed_pct,
        "draft_word_count_ceiling": draft_word_count_ceiling,
        "within_draft_surplus": within_draft_surplus,
    }


def final_acceptance_passed(
    *,
    result: Any,
    eval_status: Mapping[str, Any] | None,
    verifier_status: Mapping[str, Any] | None,
) -> bool:
    """Return the existing strict final-manuscript acceptance decision."""
    return (
        result.passed
        and result.go_scenes == result.planned_scene_count
        and result.force_resolved_scenes == 0
        and (eval_status is None or bool(eval_status.get("passed")))
        and (verifier_status is None or bool(verifier_status.get("passed")))
    )


def select_acceptance_passed(
    *,
    acceptance_mode: AcceptanceMode,
    draft_acceptance_status: Mapping[str, Any],
    result: Any,
    eval_status: Mapping[str, Any] | None,
    verifier_status: Mapping[str, Any] | None,
) -> bool:
    """Select top-level acceptance according to the requested acceptance mode."""
    if acceptance_mode == "draft":
        return bool(draft_acceptance_status.get("passed"))
    if acceptance_mode == "final":
        return final_acceptance_passed(
            result=result,
            eval_status=eval_status,
            verifier_status=verifier_status,
        )
    raise ValueError(f"Unknown acceptance mode: {acceptance_mode}")


def write_router_config_for_tier(base_config_path: Path, output_dir: Path, model_tier: str) -> Path:
    """Write a run-local ModelRouter config with the requested active tier."""
    payload: dict[str, Any] = json.loads(base_config_path.read_text(encoding="utf-8"))
    if model_tier not in payload.get("tiers", {}):
        raise ValueError(f"Unknown model tier: {model_tier}")
    payload["model_tier"] = model_tier
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = output_dir / "model_router.run.json"
    config_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return config_path


def write_files_api_fixture_assets(layout: ProjectLayout) -> dict[str, Path]:
    """Create run-local long-context fixture assets for optional Files API upload."""
    bible_path = layout.series_bible_path()
    voice_profile_path = layout.series_voice_profile_path()
    character_dir = layout.character_sheets_dir()

    bible_path.parent.mkdir(parents=True, exist_ok=True)
    voice_profile_path.parent.mkdir(parents=True, exist_ok=True)
    character_dir.mkdir(parents=True, exist_ok=True)

    bible_path.write_text(
        "# Series Bible\n\n"
        "Emma Chen is an architect trying to protect a waterfront renovation.\n"
        "Marcus Rivera is a chef defending his family cafe.\n"
        "The central promise is a rivals-to-lovers renovation romance with an HEA.\n",
        encoding="utf-8",
    )
    voice_profile_path.write_text(
        "profile_id: short-book-fixture-voice\n"
        "display_name: Short Book Fixture Voice\n"
        "style_notes:\n"
        "  - concrete sensory grounding\n"
        "  - emotionally direct dialogue\n"
        "  - no melodramatic abstraction\n",
        encoding="utf-8",
    )
    (character_dir / "emma_chen.md").write_text(
        "# Emma Chen\n\nArchitect. Precise, guarded, and quietly sentimental.\n",
        encoding="utf-8",
    )
    (character_dir / "marcus_rivera.md").write_text(
        "# Marcus Rivera\n\nChef. Loyal, practical, and protective of the family cafe.\n",
        encoding="utf-8",
    )
    return {
        "series_bible": bible_path,
        "voice_profile": voice_profile_path,
        "character_sheets": character_dir,
    }


def prepare_files_api_uploads(
    *,
    layout: ProjectLayout,
    series_id: str,
    data_root: Path,
    managed_config: ManagedAgentConfig,
    client: FilesAPIClient | None = None,
) -> dict[str, str]:
    """Upload run-local context assets and register returned Claude file IDs."""
    if not managed_config.files_api_enabled:
        return {}
    paths = write_files_api_fixture_assets(layout)
    files_client = client or FilesAPIClient(data_root=data_root)
    uploaded = files_client.upload_series_assets(
        series_id=series_id,
        series_bible_path=paths["series_bible"],
        voice_profile_path=paths["voice_profile"],
        character_sheets_dir=paths["character_sheets"],
    )
    for key, file_id in uploaded.items():
        managed_config.register_uploaded_file(key, file_id)
    return uploaded


def run_acceptance(
    *,
    fixture: FixtureName,
    model_tier: str,
    provider: str,
    output_root: Path,
    run_id: str,
    dreaming_enabled: bool,
    max_revisions: int,
    resume: bool,
    force: bool,
    run_corpus_eval: bool,
    acceptance_mode: AcceptanceMode,
    draft_surplus_allowed_pct: float,
    upload_files: bool,
    voice_threshold: float,
    ai_tell_threshold: float,
    files_api_client: FilesAPIClient | None = None,
) -> dict[str, object]:
    """Run a book fixture and return a JSON-serializable summary."""
    output_dir = output_root / run_id
    data_root = output_dir / "data"
    book_id = get_fixture_book_id(fixture)
    scenes = get_fixture_scenes(fixture)
    series_root = output_dir / "series" / SERIES_ID
    output_dir.mkdir(parents=True, exist_ok=True)
    series_root.mkdir(parents=True, exist_ok=True)

    spec = create_fixture_spec(fixture)
    layout = ProjectLayout(series_root=series_root, book_id=book_id)
    ledger_manager = LedgerManager(book_id=book_id, series_id=SERIES_ID, data_root=data_root)
    router_config_path = write_router_config_for_tier(
        WORKSPACE_ROOT / "model_router.json",
        output_dir,
        model_tier,
    )
    router = ModelRouter(
        config_path=router_config_path,
        cost_log_path=output_dir / "cost_log.jsonl",
    )
    managed_config = ManagedAgentConfig(
        managed_agent_mode=dreaming_enabled,
        dreaming_enabled=dreaming_enabled,
        files_api_enabled=upload_files,
        persistent_memory_path=output_dir / "agent_memory",
    )
    prepare_files_api_uploads(
        layout=layout,
        series_id=SERIES_ID,
        data_root=data_root,
        managed_config=managed_config,
        client=files_api_client,
    )
    agent_ctx = AgentContext(
        project_layout=layout,
        spec_loader=SpecLoader(workspace_root=WORKSPACE_ROOT),
        ledger_manager=ledger_manager,
        log_path=output_dir / "agent.log",
        output_dir=output_dir / "output",
        model_tier=model_tier,
        llm_provider=provider,
        managed_agent_config=managed_config,
    )
    runner = BookRunner(
        agent_ctx=agent_ctx,
        model_router=router,
        max_revisions=max_revisions,
        checkpoint_db_path=layout.checkpoint_db_path(),
    )
    result = runner.run_book(
        run_id=run_id,
        spec=spec,
        scenes=scenes,
        base_seed=8400,
        resume=resume,
        force=force,
        word_budget_target=get_fixture_word_count_target(fixture),
    )
    manuscript = runner.assemble_manuscript(scenes) if result.passed else None
    scene_dir = layout.book_dir() / "scenes"
    eval_status = (
        build_eval_status(
            scene_dir=scene_dir,
            model_tier=model_tier,
            voice_threshold=voice_threshold,
            ai_tell_threshold=ai_tell_threshold,
            required_scene_count=len(scenes),
        )
        if result.passed and run_corpus_eval
        else None
    )
    verifier_status = (
        build_verifier_status(result, spec, fixture=fixture) if result.passed else None
    )
    actual_word_count = (
        manuscript.word_count
        if manuscript is not None
        else sum(status.word_count for status in result.scenes)
    )
    draft_acceptance_status = build_draft_acceptance_status(
        result=result,
        target_word_count=get_fixture_word_count_target(fixture),
        actual_word_count=actual_word_count,
        eval_status=eval_status,
        draft_surplus_allowed_pct=draft_surplus_allowed_pct,
    )
    acceptance_passed = select_acceptance_passed(
        acceptance_mode=acceptance_mode,
        draft_acceptance_status=draft_acceptance_status,
        result=result,
        eval_status=eval_status,
        verifier_status=verifier_status,
    )
    payload = runner.write_book_run_summary(
        result=result,
        provider=provider,
        manuscript=manuscript,
        eval_status=eval_status,
        verifier_status=verifier_status,
        draft_acceptance_status=draft_acceptance_status,
        cost_log_path=output_dir / "cost_log.jsonl",
        extra_metadata={
            "dreaming_enabled": dreaming_enabled,
            "fixture": fixture,
            "output_dir": str(output_dir),
            "acceptance_mode": acceptance_mode,
            "acceptance_passed": acceptance_passed,
            "resume_enabled": resume,
            "force_rerun": force,
            "files_api_metadata_path": str(data_root / SERIES_ID / "file_ids.json"),
        },
    )
    return payload


def _default_run_id(model_tier: str, provider: str, fixture: str = "short") -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{fixture}_{model_tier}_{provider}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run book generation acceptance fixtures.")
    parser.add_argument(
        "--fixture",
        choices=("short", "novella"),
        default="short",
        help="Acceptance fixture to run. 'short' is the original 8-scene default.",
    )
    parser.add_argument("--model-tier", choices=("test", "production"), default="test")
    parser.add_argument(
        "--provider",
        choices=("openai", "anthropic", "ollama"),
        default=os.getenv("FF_LLM_PROVIDER", "openai"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=WORKSPACE_ROOT / "data" / "book_acceptance",
    )
    parser.add_argument("--run-id", help="Stable run ID. Defaults to timestamp_tier_provider.")
    parser.add_argument("--with-dreaming", action="store_true", help="Enable managed memory.")
    parser.add_argument("--max-revisions", type=int, default=1)
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip completed scenes with existing final outputs. Enabled by default.",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate all scenes intentionally.")
    parser.add_argument(
        "--upload-files",
        action="store_true",
        help="Upload run-local bible/profile/character assets to Claude Files API.",
    )
    parser.add_argument(
        "--eval",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run deterministic corpus eval after scene generation/resume.",
    )
    parser.add_argument(
        "--acceptance-mode",
        choices=("draft", "final"),
        default="draft",
        help="Choose draft surplus acceptance or strict final verifier acceptance.",
    )
    parser.add_argument(
        "--draft-surplus-allowed-pct",
        type=float,
        default=DEFAULT_DRAFT_SURPLUS_ALLOWED_PCT,
        help="Allowed draft surplus over target as a decimal; 0.25 means +25%.",
    )
    parser.add_argument("--voice-threshold", type=float, default=0.75)
    parser.add_argument("--ai-tell-threshold", type=float, default=0.50)
    parser.add_argument("--json", action="store_true", help="Print summary JSON only.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.draft_surplus_allowed_pct < 0:
        parser.error("--draft-surplus-allowed-pct must be non-negative")
    logging.basicConfig(
        level=logging.WARNING if args.json else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run_id = args.run_id or _default_run_id(args.model_tier, args.provider, args.fixture)
    try:
        payload = run_acceptance(
            fixture=args.fixture,
            model_tier=args.model_tier,
            provider=args.provider,
            output_root=args.output_root,
            run_id=run_id,
            dreaming_enabled=args.with_dreaming,
            max_revisions=args.max_revisions,
            resume=args.resume,
            force=args.force,
            run_corpus_eval=args.eval,
            acceptance_mode=args.acceptance_mode,
            draft_surplus_allowed_pct=args.draft_surplus_allowed_pct,
            upload_files=args.upload_files,
            voice_threshold=args.voice_threshold,
            ai_tell_threshold=args.ai_tell_threshold,
        )
    except Exception as exc:
        logger.error("Book acceptance failed: %s", exc, exc_info=True)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Book Acceptance")
        print(f"Run: {payload['run_id']}")
        print(f"Fixture: {payload['fixture']}")
        print(f"Tier/provider: {payload['model_tier']}/{payload['provider']}")
        print(f"Acceptance mode: {payload['acceptance_mode']}")
        print(f"Scenes: {payload['successful_scenes']}/{payload['planned_scene_count']} completed")
        print(f"GO decisions: {payload['go_scenes']}/{payload['planned_scene_count']}")
        print(f"Force-resolved: {payload['force_resolved_scenes']}")
        eval_status = payload.get("eval_status")
        if isinstance(eval_status, dict):
            print(
                f"Eval: {'PASS' if eval_status['passed'] else 'FAIL'} "
                f"({eval_status['scene_count']} scenes)"
            )
        verifier_status = payload.get("verifier_status")
        if isinstance(verifier_status, dict):
            print(f"Verifier: {'PASS' if verifier_status['passed'] else 'FAIL'}")
        draft_status = payload.get("draft_acceptance_status")
        if isinstance(draft_status, dict):
            print(
                "Draft acceptance: "
                f"{'PASS' if draft_status['passed'] else 'FAIL'} "
                f"({draft_status['classification']}; "
                f"{draft_status['actual_word_count']}/"
                f"{draft_status['target_word_count']} words, "
                f"surplus {draft_status['surplus_pct']:.2%} <= "
                f"{draft_status['draft_surplus_allowed_pct']:.2%})"
            )
        word_budget_status = payload.get("word_budget_status")
        if isinstance(word_budget_status, dict) and word_budget_status.get("enabled"):
            print(
                "Word budget: "
                f"{word_budget_status['actual_word_count']}/"
                f"{word_budget_status['book_word_count_target']} words, "
                f"projected {word_budget_status['projected_final_count']}, "
                f"min scene target {word_budget_status['min_scene_target']}"
            )
        print(f"Status: {payload['status_path']}")
        print(f"Output: {payload['output_dir']}")
        print(f"Result: {'PASS' if payload['acceptance_passed'] else 'FAIL'}")

    return 0 if payload["acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
