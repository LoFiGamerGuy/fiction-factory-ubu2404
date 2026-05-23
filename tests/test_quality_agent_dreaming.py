"""Test QualityAgent with Claude Managed Agents (Dreaming) support.

BCR-20260522-claude-dreaming-mem0 Phase 7 T7.4
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pipeline.agents.quality_agent import QualityAgent
from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
from pipeline.core.managed_agent_config import ManagedAgentConfig
from pipeline.core.project_layout import ProjectLayout
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.profiles.project_spec import ProjectSpec

if TYPE_CHECKING:
    pass


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
def agent_context_dreaming(
    tmp_path: Path,
    managed_config_dreaming: ManagedAgentConfig,
    mock_project_spec: ProjectSpec,
) -> AgentContext:
    """AgentContext with Dreaming enabled."""
    series_root = tmp_path / "data" / "series" / "test-series"
    series_root.mkdir(parents=True, exist_ok=True)

    project_layout = ProjectLayout(
        series_root=series_root,
        book_id="test-book-01",
    )
    ledger_manager = LedgerManager(
        book_id="test-book-01",
        series_id="test-series",
        data_root=tmp_path / "data",
    )

    # Create minimal SpecLoader mock
    from unittest.mock import MagicMock

    spec_loader = MagicMock()
    spec_loader.load_series_spec.return_value = mock_project_spec

    return AgentContext(
        project_layout=project_layout,
        spec_loader=spec_loader,
        ledger_manager=ledger_manager,
        managed_agent_config=managed_config_dreaming,
        log_path=tmp_path / "agent.log",
        output_dir=tmp_path / "output",
        model_tier="test",
    )


@pytest.fixture
def agent_context_no_dreaming(
    tmp_path: Path,
    managed_config_no_dreaming: ManagedAgentConfig,
    mock_project_spec: ProjectSpec,
) -> AgentContext:
    """AgentContext with Dreaming disabled."""
    series_root = tmp_path / "data" / "series" / "test-series"
    series_root.mkdir(parents=True, exist_ok=True)

    project_layout = ProjectLayout(
        series_root=series_root,
        book_id="test-book-01",
    )
    ledger_manager = LedgerManager(
        book_id="test-book-01",
        series_id="test-series",
        data_root=tmp_path / "data",
    )

    # Create minimal SpecLoader mock
    from unittest.mock import MagicMock

    spec_loader = MagicMock()
    spec_loader.load_series_spec.return_value = mock_project_spec

    return AgentContext(
        project_layout=project_layout,
        spec_loader=spec_loader,
        ledger_manager=ledger_manager,
        managed_agent_config=managed_config_no_dreaming,
        log_path=tmp_path / "agent.log",
        output_dir=tmp_path / "output",
        model_tier="test",
    )


def test_quality_agent_with_dreaming_instantiation(
    agent_context_dreaming: AgentContext,
) -> None:
    """Test QualityAgent instantiates with Dreaming enabled."""
    agent = QualityAgent(agent_context_dreaming)
    assert agent is not None
    assert agent.ctx.managed_agent_config is not None
    assert agent.ctx.managed_agent_config.dreaming_enabled is True


def test_quality_agent_without_dreaming_instantiation(
    agent_context_no_dreaming: AgentContext,
) -> None:
    """Test QualityAgent instantiates with Dreaming disabled."""
    agent = QualityAgent(agent_context_no_dreaming)
    assert agent is not None
    assert agent.ctx.managed_agent_config is not None
    assert agent.ctx.managed_agent_config.dreaming_enabled is False


def test_quality_agent_memory_persistence_with_dreaming(
    agent_context_dreaming: AgentContext,
    mock_project_spec: ProjectSpec,
) -> None:
    """Test QualityAgent persists memory when Dreaming enabled."""
    agent = QualityAgent(agent_context_dreaming)

    # Create job context with editor output
    job_ctx = JobContext(
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

    # Add editor output (clean scene)
    job_ctx = job_ctx.with_output(
        "editor_agent",
        {
            "edited_text": "This is a test scene with sufficient content. " * 50,  # ~350 words
            "nofly_violations": 0,
            "structural_flags": 0,
            "is_clean": True,
        },
    )

    # Execute agent (quality evaluation)
    result = agent.run(job_ctx)

    assert result is not None
    assert "quality_agent" in result.output_data

    # Check memory file was created
    memory_file = agent_context_dreaming.managed_agent_config.get_memory_file("QualityAgent")
    assert memory_file.exists()

    # Verify memory contents
    memory_data = json.loads(memory_file.read_text(encoding="utf-8"))
    assert memory_data["scenes_evaluated"] == 1
    assert "total_pass" in memory_data
    assert "total_warn" in memory_data
    assert "total_fail" in memory_data
    assert "pass_rate" in memory_data
    assert "recent_scenes" in memory_data
    assert len(memory_data["recent_scenes"]) == 1
    assert memory_data["recent_scenes"][0]["scene_id"] == "scene_01"


def test_quality_agent_no_memory_persistence_without_dreaming(
    agent_context_no_dreaming: AgentContext,
    mock_project_spec: ProjectSpec,
) -> None:
    """Test QualityAgent does NOT persist memory when Dreaming disabled."""
    agent = QualityAgent(agent_context_no_dreaming)

    # Create job context
    job_ctx = JobContext(
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

    # Add editor output
    job_ctx = job_ctx.with_output(
        "editor_agent",
        {
            "edited_text": "Test scene content. " * 50,
            "nofly_violations": 0,
            "structural_flags": 0,
            "is_clean": True,
        },
    )

    # Execute agent
    result = agent.run(job_ctx)

    assert result is not None
    assert "quality_agent" in result.output_data

    # Verify managed_agent_mode is False (Dreaming disabled)
    assert agent_context_no_dreaming.managed_agent_config.managed_agent_mode is False
    assert agent_context_no_dreaming.managed_agent_config.dreaming_enabled is False


def test_quality_agent_multiple_scenes_accumulate_memory(
    agent_context_dreaming: AgentContext,
    mock_project_spec: ProjectSpec,
) -> None:
    """Test QualityAgent accumulates memory across multiple scenes."""
    agent = QualityAgent(agent_context_dreaming)

    # Evaluate 3 scenes
    for i in range(1, 4):
        job_ctx = JobContext(
            job_id=f"test_job_{i}",
            series_id="test-series",
            book_id="test-book-01",
            chapter_id=1,
            scene_id=f"scene_{i:02d}",
            spec=mock_project_spec,
            model_tier="test",
            seed=42 + i,
            scene_brief=f"Test scene {i}",
            word_count_target=1000,
            heat_level=2,
        )

        job_ctx = job_ctx.with_output(
            "editor_agent",
            {
                "edited_text": f"Scene {i} content. " * 50,
                "nofly_violations": i % 2,  # Alternating clean/nofly
                "structural_flags": 0,
                "is_clean": i % 2 == 0,
            },
        )

        agent.run(job_ctx)

    # Verify accumulated memory
    memory_file = agent_context_dreaming.managed_agent_config.get_memory_file("QualityAgent")
    memory_data = json.loads(memory_file.read_text(encoding="utf-8"))

    assert memory_data["scenes_evaluated"] == 3
    assert len(memory_data["recent_scenes"]) == 3
    assert memory_data["recent_scenes"][0]["scene_id"] == "scene_01"
    assert memory_data["recent_scenes"][1]["scene_id"] == "scene_02"
    assert memory_data["recent_scenes"][2]["scene_id"] == "scene_03"


def test_quality_agent_pass_rate_calculation(
    agent_context_dreaming: AgentContext,
    mock_project_spec: ProjectSpec,
) -> None:
    """Test QualityAgent calculates pass rate correctly."""
    agent = QualityAgent(agent_context_dreaming)

    # Scene 1: PASS (clean)
    job_ctx1 = JobContext(
        job_id="test_job_1",
        series_id="test-series",
        book_id="test-book-01",
        chapter_id=1,
        scene_id="scene_01",
        spec=mock_project_spec,
        model_tier="test",
        seed=42,
        scene_brief="Clean scene",
        word_count_target=1000,
        heat_level=2,
    )
    job_ctx1 = job_ctx1.with_output(
        "editor_agent",
        {
            "edited_text": "Clean content. " * 50,
            "nofly_violations": 0,
            "structural_flags": 0,
            "is_clean": True,
        },
    )
    agent.run(job_ctx1)

    # Scene 2: FAIL (nofly violations)
    job_ctx2 = JobContext(
        job_id="test_job_2",
        series_id="test-series",
        book_id="test-book-01",
        chapter_id=1,
        scene_id="scene_02",
        spec=mock_project_spec,
        model_tier="test",
        seed=43,
        scene_brief="Problematic scene",
        word_count_target=1000,
        heat_level=2,
    )
    job_ctx2 = job_ctx2.with_output(
        "editor_agent",
        {
            "edited_text": "Problematic content. " * 50,
            "nofly_violations": 10,
            "structural_flags": 8,
            "is_clean": False,
        },
    )
    agent.run(job_ctx2)

    # Verify pass rate: 1 pass out of 2 = 50%
    memory_file = agent_context_dreaming.managed_agent_config.get_memory_file("QualityAgent")
    memory_data = json.loads(memory_file.read_text(encoding="utf-8"))

    assert memory_data["scenes_evaluated"] == 2
    assert memory_data["total_pass"] == 1
    assert memory_data["total_fail"] == 1
    assert memory_data["pass_rate"] == 0.5
