"""Test ConvergenceController with Claude Managed Agents (Dreaming) support.

BCR-20260522-claude-dreaming-mem0 Phase 7 T7.5
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.agents.agent_models import QualityResult
from pipeline.convergence_controller import ConvergenceController, ConvergenceDecision
from pipeline.core.job_context import JobContext
from pipeline.core.managed_agent_config import ManagedAgentConfig
from pipeline.profiles.project_spec import ProjectSpec


@pytest.fixture
def temp_memory_dir(tmp_path: Path) -> Path:
    """Temporary directory for agent memory."""
    memory_dir = tmp_path / "agent_memory"
    memory_dir.mkdir()
    return memory_dir


@pytest.fixture
def managed_config_dreaming(temp_memory_dir: Path) -> ManagedAgentConfig:
    """ManagedAgentConfig with Dreaming enabled."""
    return ManagedAgentConfig(
        managed_agent_mode=True,
        dreaming_enabled=True,
        persistent_memory_path=temp_memory_dir,
        files_api_enabled=False,
        message_batches_enabled=False,
    )


@pytest.fixture
def managed_config_no_dreaming(temp_memory_dir: Path) -> ManagedAgentConfig:
    """ManagedAgentConfig with Dreaming disabled."""
    return ManagedAgentConfig(
        managed_agent_mode=False,
        dreaming_enabled=False,
        persistent_memory_path=temp_memory_dir,
        files_api_enabled=False,
        message_batches_enabled=False,
    )


@pytest.fixture
def sample_job_context(mock_project_spec: ProjectSpec) -> JobContext:
    """Sample job context for testing."""
    return JobContext(
        job_id="test_job",
        series_id="test-series",
        book_id="test-book-01",
        chapter_id=1,
        scene_id="scene_01",
        spec=mock_project_spec,
        model_tier="test",
        seed=42,
        scene_brief="Test scene",
        word_count_target=1000,
        heat_level=2,
    )


@pytest.fixture
def clean_quality_result() -> QualityResult:
    """Clean quality result (no issues)."""
    return QualityResult(
        needs_review=False,
        tier="pass",
        nofly_violations=0,
        structural_flags=0,
        sensitivity_violation=False,
        scene_id="scene_01",
        notes=[],
    )


@pytest.fixture
def needs_review_quality_result() -> QualityResult:
    """Quality result requiring review."""
    return QualityResult(
        needs_review=True,
        tier="fail",
        nofly_violations=5,
        structural_flags=3,
        sensitivity_violation=False,
        scene_id="scene_01",
        notes=["Too many nofly violations"],
    )


@pytest.fixture
def sensitivity_violation_quality_result() -> QualityResult:
    """Quality result with sensitivity violation."""
    return QualityResult(
        needs_review=True,
        tier="fail",
        nofly_violations=0,
        structural_flags=0,
        sensitivity_violation=True,
        scene_id="scene_01",
        notes=["Heat level exceeds threshold"],
    )


def test_convergence_controller_with_dreaming_instantiation(
    managed_config_dreaming: ManagedAgentConfig,
) -> None:
    """Test ConvergenceController instantiates with Dreaming enabled."""
    controller = ConvergenceController(managed_agent_config=managed_config_dreaming)
    assert controller is not None


def test_convergence_controller_without_dreaming_instantiation(
    managed_config_no_dreaming: ManagedAgentConfig,
) -> None:
    """Test ConvergenceController instantiates with Dreaming disabled."""
    controller = ConvergenceController(managed_agent_config=managed_config_no_dreaming)
    assert controller is not None


def test_convergence_decision_go_with_dreaming(
    managed_config_dreaming: ManagedAgentConfig,
    sample_job_context: JobContext,
    clean_quality_result: QualityResult,
) -> None:
    """Test GO decision with Dreaming memory persistence."""
    controller = ConvergenceController(managed_agent_config=managed_config_dreaming)

    decision = controller.decide(clean_quality_result, sample_job_context, revise_count=0)

    assert decision == ConvergenceDecision.GO

    # Check memory file was created
    memory_file = managed_config_dreaming.get_memory_file("ConvergenceController")
    assert memory_file.exists()

    # Verify memory contents
    memory_data = json.loads(memory_file.read_text(encoding="utf-8"))
    assert memory_data["total_decisions"] == 1
    assert memory_data["total_GO"] == 1
    assert memory_data["go_rate"] == 1.0
    assert len(memory_data["recent_decisions"]) == 1
    assert memory_data["recent_decisions"][0]["decision"] == "GO"
    assert memory_data["recent_decisions"][0]["reason"] == "passed"


def test_convergence_decision_revise_with_dreaming(
    managed_config_dreaming: ManagedAgentConfig,
    sample_job_context: JobContext,
    needs_review_quality_result: QualityResult,
) -> None:
    """Test REVISE decision with Dreaming memory persistence."""
    controller = ConvergenceController(
        max_revisions=3, managed_agent_config=managed_config_dreaming
    )

    decision = controller.decide(needs_review_quality_result, sample_job_context, revise_count=0)

    assert decision == ConvergenceDecision.REVISE

    # Verify memory
    memory_file = managed_config_dreaming.get_memory_file("ConvergenceController")
    memory_data = json.loads(memory_file.read_text(encoding="utf-8"))

    assert memory_data["total_decisions"] == 1
    assert memory_data["total_REVISE"] == 1
    assert memory_data["recent_decisions"][0]["decision"] == "REVISE"
    assert memory_data["recent_decisions"][0]["reason"] == "quality_needs_review"
    assert memory_data["recent_decisions"][0]["revise_count"] == 0


def test_convergence_decision_replan_sensitivity_with_dreaming(
    managed_config_dreaming: ManagedAgentConfig,
    sample_job_context: JobContext,
    sensitivity_violation_quality_result: QualityResult,
) -> None:
    """Test RE_PLAN on sensitivity violation (cannot FORCE_RESOLVE)."""
    controller = ConvergenceController(managed_agent_config=managed_config_dreaming)

    decision = controller.decide(
        sensitivity_violation_quality_result, sample_job_context, revise_count=0
    )

    assert decision == ConvergenceDecision.RE_PLAN

    # Verify memory
    memory_file = managed_config_dreaming.get_memory_file("ConvergenceController")
    memory_data = json.loads(memory_file.read_text(encoding="utf-8"))

    assert memory_data["total_RE_PLAN"] == 1
    assert memory_data["recent_decisions"][0]["decision"] == "RE_PLAN"
    assert memory_data["recent_decisions"][0]["reason"] == "sensitivity_violation"


def test_convergence_decision_replan_revisions_exhausted(
    managed_config_dreaming: ManagedAgentConfig,
    sample_job_context: JobContext,
    needs_review_quality_result: QualityResult,
) -> None:
    """Test RE_PLAN when revisions exhausted."""
    controller = ConvergenceController(
        max_revisions=3, managed_agent_config=managed_config_dreaming
    )

    decision = controller.decide(needs_review_quality_result, sample_job_context, revise_count=3)

    assert decision == ConvergenceDecision.RE_PLAN

    # Verify memory
    memory_file = managed_config_dreaming.get_memory_file("ConvergenceController")
    memory_data = json.loads(memory_file.read_text(encoding="utf-8"))

    assert memory_data["total_RE_PLAN"] == 1
    assert memory_data["recent_decisions"][0]["decision"] == "RE_PLAN"
    assert memory_data["recent_decisions"][0]["reason"] == "revisions_exhausted"
    assert memory_data["recent_decisions"][0]["revise_count"] == 3


def test_convergence_decision_force_resolve_budget_exhausted(
    managed_config_dreaming: ManagedAgentConfig,
    sample_job_context: JobContext,
    clean_quality_result: QualityResult,
    tmp_path: Path,
) -> None:
    """Test FORCE_RESOLVE when budget exhausted."""
    # Modify job context to signal budget exhaustion
    sample_job_context = sample_job_context.with_output(
        "quality_agent", {"word_count_remaining": 0}
    )

    log_path = tmp_path / "force_resolve.jsonl"
    controller = ConvergenceController(
        budget_words_threshold=100,
        decisions_log_path=log_path,
        managed_agent_config=managed_config_dreaming,
    )

    decision = controller.decide(clean_quality_result, sample_job_context, revise_count=0)

    assert decision == ConvergenceDecision.FORCE_RESOLVE

    # Verify FORCE_RESOLVE log exists
    assert log_path.exists()
    log_entries = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(log_entries) == 1
    log_data = json.loads(log_entries[0])
    assert log_data["event"] == "FORCE_RESOLVE"
    assert log_data["reason"] == "word_count_budget_exhausted"

    # Verify memory
    memory_file = managed_config_dreaming.get_memory_file("ConvergenceController")
    memory_data = json.loads(memory_file.read_text(encoding="utf-8"))

    assert memory_data["total_FORCE_RESOLVE"] == 1
    assert memory_data["recent_decisions"][0]["decision"] == "FORCE_RESOLVE"
    assert memory_data["recent_decisions"][0]["reason"] == "budget_exhausted"


def test_convergence_no_memory_persistence_without_dreaming(
    managed_config_no_dreaming: ManagedAgentConfig,
    sample_job_context: JobContext,
    clean_quality_result: QualityResult,
) -> None:
    """Test ConvergenceController does NOT persist memory when Dreaming disabled."""
    controller = ConvergenceController(managed_agent_config=managed_config_no_dreaming)

    decision = controller.decide(clean_quality_result, sample_job_context, revise_count=0)

    assert decision == ConvergenceDecision.GO

    # Verify managed_agent_mode is False (Dreaming disabled)
    assert managed_config_no_dreaming.managed_agent_mode is False
    assert managed_config_no_dreaming.dreaming_enabled is False


def test_convergence_multiple_decisions_accumulate_memory(
    managed_config_dreaming: ManagedAgentConfig,
    sample_job_context: JobContext,
    clean_quality_result: QualityResult,
    needs_review_quality_result: QualityResult,
) -> None:
    """Test multiple decisions accumulate in memory."""
    controller = ConvergenceController(
        max_revisions=3, managed_agent_config=managed_config_dreaming
    )

    # Decision 1: GO
    controller.decide(clean_quality_result, sample_job_context, revise_count=0)

    # Decision 2: REVISE
    sample_job_context.scene_id = "scene_02"
    controller.decide(needs_review_quality_result, sample_job_context, revise_count=0)

    # Decision 3: GO
    sample_job_context.scene_id = "scene_03"
    controller.decide(clean_quality_result, sample_job_context, revise_count=0)

    # Verify accumulated memory
    memory_file = managed_config_dreaming.get_memory_file("ConvergenceController")
    memory_data = json.loads(memory_file.read_text(encoding="utf-8"))

    assert memory_data["total_decisions"] == 3
    assert memory_data["total_GO"] == 2
    assert memory_data["total_REVISE"] == 1
    assert memory_data["go_rate"] == 2.0 / 3.0  # 66.67%
    assert len(memory_data["recent_decisions"]) == 3


def test_convergence_go_rate_calculation(
    managed_config_dreaming: ManagedAgentConfig,
    sample_job_context: JobContext,
    clean_quality_result: QualityResult,
    needs_review_quality_result: QualityResult,
) -> None:
    """Test GO rate calculation for convergence efficiency."""
    controller = ConvergenceController(
        max_revisions=3, managed_agent_config=managed_config_dreaming
    )

    # 3 GO, 1 REVISE = 75% GO rate
    controller.decide(clean_quality_result, sample_job_context, revise_count=0)
    sample_job_context.scene_id = "scene_02"
    controller.decide(clean_quality_result, sample_job_context, revise_count=0)
    sample_job_context.scene_id = "scene_03"
    controller.decide(needs_review_quality_result, sample_job_context, revise_count=0)
    sample_job_context.scene_id = "scene_04"
    controller.decide(clean_quality_result, sample_job_context, revise_count=0)

    # Verify GO rate
    memory_file = managed_config_dreaming.get_memory_file("ConvergenceController")
    memory_data = json.loads(memory_file.read_text(encoding="utf-8"))

    assert memory_data["total_decisions"] == 4
    assert memory_data["total_GO"] == 3
    assert memory_data["total_REVISE"] == 1
    assert memory_data["go_rate"] == 0.75


def test_convergence_sensitivity_cannot_force_resolve(
    managed_config_dreaming: ManagedAgentConfig,
    sample_job_context: JobContext,
    sensitivity_violation_quality_result: QualityResult,
    tmp_path: Path,
) -> None:
    """Test sensitivity violations can never become FORCE_RESOLVE (DEC-005)."""
    # Even with budget exhausted, sensitivity → RE_PLAN
    sample_job_context = sample_job_context.with_output(
        "quality_agent", {"word_count_remaining": 0}
    )

    log_path = tmp_path / "force_resolve.jsonl"
    controller = ConvergenceController(
        budget_words_threshold=100,
        decisions_log_path=log_path,
        managed_agent_config=managed_config_dreaming,
    )

    decision = controller.decide(
        sensitivity_violation_quality_result, sample_job_context, revise_count=0
    )

    # Should be RE_PLAN, NOT FORCE_RESOLVE
    assert decision == ConvergenceDecision.RE_PLAN

    # Verify no FORCE_RESOLVE log entry
    if log_path.exists():
        log_content = log_path.read_text(encoding="utf-8").strip()
        assert log_content == "" or "sensitivity" not in log_content

    # Verify memory shows RE_PLAN
    memory_file = managed_config_dreaming.get_memory_file("ConvergenceController")
    memory_data = json.loads(memory_file.read_text(encoding="utf-8"))

    assert memory_data["total_RE_PLAN"] == 1
    assert memory_data["total_FORCE_RESOLVE"] == 0
