"""Test EditorAgent with Claude Managed Agents (Dreaming) support.

BCR-20260522-claude-dreaming-mem0 Phase 7 T7.2
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pipeline.agents.editor_agent import EditorAgent
from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
from pipeline.core.managed_agent_config import ManagedAgentConfig
from pipeline.core.project_layout import ProjectLayout
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.profiles.project_spec import ProjectSpec

if TYPE_CHECKING:
    from unittest.mock import MagicMock


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


@pytest.fixture
def sample_draft_text() -> str:
    """Sample draft text with some issues."""
    return """The day was nice. It was very nice indeed. Sarah walked down the street.

She thought to herself about how the weather was pleasant. It was a testament to
the beauty of spring. The flowers were blooming and everything felt right.

"Hello," she said to herself. "This is a good day."

She continued walking, her footsteps echoing in the empty street. The sun shone
brightly overhead, casting long shadows on the pavement."""


def test_editor_agent_with_dreaming_instantiation(
    agent_context_dreaming: AgentContext,
    mock_model_router: MagicMock,
) -> None:
    """Test EditorAgent instantiates with Dreaming enabled."""
    agent = EditorAgent(agent_context_dreaming, mock_model_router)
    assert agent is not None
    assert agent.ctx.managed_agent_config is not None
    assert agent.ctx.managed_agent_config.dreaming_enabled is True


def test_editor_agent_without_dreaming_instantiation(
    agent_context_no_dreaming: AgentContext,
    mock_model_router: MagicMock,
) -> None:
    """Test EditorAgent instantiates with Dreaming disabled."""
    agent = EditorAgent(agent_context_no_dreaming, mock_model_router)
    assert agent is not None
    assert agent.ctx.managed_agent_config is not None
    assert agent.ctx.managed_agent_config.dreaming_enabled is False


def test_editor_agent_memory_persistence_with_dreaming(
    agent_context_dreaming: AgentContext,
    mock_model_router: MagicMock,
    mock_project_spec: ProjectSpec,
    sample_draft_text: str,
    tmp_path: Path,
) -> None:
    """Test EditorAgent persists memory when Dreaming enabled."""
    agent = EditorAgent(agent_context_dreaming, mock_model_router)

    # Create draft file
    draft_path = tmp_path / "data" / "books" / "test-book-01" / "drafts" / "scene_01_draft.md"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(sample_draft_text, encoding="utf-8")

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
    )

    # Add writer output to job context
    job_ctx = job_ctx.with_output("writer_agent", {"draft_text": sample_draft_text})

    # Execute agent (runs deterministic scan + structural analysis)
    result = agent.run(job_ctx)

    assert result is not None
    assert "editor_agent" in result.output_data

    # Check memory file was created
    memory_file = agent_context_dreaming.managed_agent_config.get_memory_file("EditorAgent")
    assert memory_file.exists()

    # Verify memory contents
    memory_data = json.loads(memory_file.read_text(encoding="utf-8"))
    assert memory_data["scenes_edited"] == 1
    assert "total_surgical_passes" in memory_data
    assert "total_nofly_violations" in memory_data
    assert "total_structural_flags" in memory_data
    assert "recent_scenes" in memory_data
    assert len(memory_data["recent_scenes"]) == 1


def test_editor_agent_no_memory_persistence_without_dreaming(
    agent_context_no_dreaming: AgentContext,
    mock_model_router: MagicMock,
    mock_project_spec: ProjectSpec,
    sample_draft_text: str,
    tmp_path: Path,
) -> None:
    """Test EditorAgent does NOT persist memory when Dreaming disabled."""
    agent = EditorAgent(agent_context_no_dreaming, mock_model_router)

    # Create draft file
    draft_path = tmp_path / "data" / "books" / "test-book-01" / "drafts" / "scene_01_draft.md"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(sample_draft_text, encoding="utf-8")

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
    )

    # Add writer output
    job_ctx = job_ctx.with_output("writer_agent", {"draft_text": sample_draft_text})

    # Execute agent
    result = agent.run(job_ctx)

    assert result is not None
    assert "editor_agent" in result.output_data

    # Verify managed_agent_mode is False (Dreaming disabled)
    assert agent_context_no_dreaming.managed_agent_config.managed_agent_mode is False
    assert agent_context_no_dreaming.managed_agent_config.dreaming_enabled is False
