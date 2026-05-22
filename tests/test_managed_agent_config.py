"""Tests for Claude Managed Agents configuration (T1.12).

BCR-20260522-claude-dreaming-mem0
"""

from pathlib import Path

import pytest

from pipeline.core.agent_context import AgentContext
from pipeline.core.managed_agent_config import ManagedAgentConfig
from pipeline.core.project_layout import ProjectLayout
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.profiles.spec_loader import SpecLoader


class TestManagedAgentConfigConstruction:
    """T1.12: Fixture test — AgentContext instantiates with managed_agent_mode=True/False."""

    def test_agent_context_managed_mode_false(self, tmp_path: Path) -> None:
        """AgentContext with managed_agent_mode=False (default)."""
        layout = ProjectLayout(series_root=tmp_path, book_id="test-book")
        spec_loader = SpecLoader(workspace_root=tmp_path)
        ledger_manager = LedgerManager(book_id="test-book", data_root=tmp_path / "ledgers")

        ctx = AgentContext(
            project_layout=layout,
            spec_loader=spec_loader,
            ledger_manager=ledger_manager,
            log_path=tmp_path / "agent.log",
            output_dir=tmp_path / "output",
        )

        assert ctx.managed_agent_config.managed_agent_mode is False
        assert ctx.managed_agent_config.persistent_memory_path is None
        assert ctx.managed_agent_config.dreaming_enabled is False

    def test_agent_context_managed_mode_true(self, tmp_path: Path) -> None:
        """AgentContext with managed_agent_mode=True."""
        layout = ProjectLayout(series_root=tmp_path, book_id="test-book")
        spec_loader = SpecLoader(workspace_root=tmp_path)
        ledger_manager = LedgerManager(book_id="test-book", data_root=tmp_path / "ledgers")

        memory_path = tmp_path / "agent_memory"
        config = ManagedAgentConfig(
            managed_agent_mode=True,
            persistent_memory_path=memory_path,
        )

        ctx = AgentContext(
            project_layout=layout,
            spec_loader=spec_loader,
            ledger_manager=ledger_manager,
            log_path=tmp_path / "agent.log",
            output_dir=tmp_path / "output",
            managed_agent_config=config,
        )

        assert ctx.managed_agent_config.managed_agent_mode is True
        assert ctx.managed_agent_config.persistent_memory_path == memory_path
        assert memory_path.exists()

    def test_managed_mode_requires_memory_path(self) -> None:
        """managed_agent_mode=True without persistent_memory_path raises ValueError."""
        with pytest.raises(ValueError, match="requires persistent_memory_path"):
            ManagedAgentConfig(managed_agent_mode=True)

    def test_dreaming_requires_managed_mode(self, tmp_path: Path) -> None:
        """dreaming_enabled=True without managed_agent_mode raises ValueError."""
        with pytest.raises(ValueError, match="requires managed_agent_mode=True"):
            ManagedAgentConfig(
                managed_agent_mode=False,
                dreaming_enabled=True,
            )


class TestManagedAgentMemoryFiles:
    """Memory file management."""

    def test_get_memory_file(self, tmp_path: Path) -> None:
        """get_memory_file() returns agent-specific path."""
        config = ManagedAgentConfig(
            managed_agent_mode=True,
            persistent_memory_path=tmp_path / "memory",
        )

        writer_memory = config.get_memory_file("WriterAgent")
        assert writer_memory == tmp_path / "memory" / "WriterAgent.memory.json"

        editor_memory = config.get_memory_file("EditorAgent")
        assert editor_memory == tmp_path / "memory" / "EditorAgent.memory.json"

    def test_get_memory_file_without_managed_mode(self) -> None:
        """get_memory_file() without managed_agent_mode raises ValueError."""
        config = ManagedAgentConfig(managed_agent_mode=False)

        with pytest.raises(ValueError, match="requires managed_agent_mode=True"):
            config.get_memory_file("WriterAgent")


class TestFilesAPISupport:
    """Files API upload registration (Phase 6 preparation)."""

    def test_register_and_retrieve_file_id(self, tmp_path: Path) -> None:
        """Files API file ID registration and retrieval."""
        config = ManagedAgentConfig(
            managed_agent_mode=True,
            persistent_memory_path=tmp_path / "memory",
            files_api_enabled=True,
        )

        config.register_uploaded_file("series_bible", "file-abc123")
        config.register_uploaded_file("voice_profile", "file-xyz789")

        assert config.get_file_id("series_bible") == "file-abc123"
        assert config.get_file_id("voice_profile") == "file-xyz789"
        assert config.get_file_id("nonexistent") is None

    def test_register_file_without_files_api_enabled(self, tmp_path: Path) -> None:
        """register_uploaded_file() without files_api_enabled raises ValueError."""
        config = ManagedAgentConfig(
            managed_agent_mode=True,
            persistent_memory_path=tmp_path / "memory",
            files_api_enabled=False,
        )

        with pytest.raises(ValueError, match="requires files_api_enabled=True"):
            config.register_uploaded_file("series_bible", "file-abc123")


class TestDreamingMode:
    """Dreaming enablement flag."""

    def test_dreaming_enabled_with_managed_mode(self, tmp_path: Path) -> None:
        """Dreaming can be enabled when managed_agent_mode=True."""
        config = ManagedAgentConfig(
            managed_agent_mode=True,
            persistent_memory_path=tmp_path / "memory",
            dreaming_enabled=True,
        )

        assert config.dreaming_enabled is True
        assert config.managed_agent_mode is True
