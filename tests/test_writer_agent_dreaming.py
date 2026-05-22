"""Tests for WriterAgent with Claude Managed Agents Dreaming.

BCR-20260522-claude-dreaming-mem0 - Phase 7 T7.1 wiring
"""

import json
from pathlib import Path
from unittest.mock import Mock

from pipeline.agents.agent_models import WriterOutput
from pipeline.agents.writer_agent import WriterAgent
from pipeline.core.agent_context import AgentContext
from pipeline.core.managed_agent_config import ManagedAgentConfig
from pipeline.core.model_router import ModelRouter
from pipeline.core.project_layout import ProjectLayout
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.profiles.spec_loader import SpecLoader


class TestWriterAgentDreamingWiring:
    """Verify WriterAgent is wired for managed_agent_config."""

    def test_writer_agent_with_dreaming_disabled(self, tmp_path: Path) -> None:
        """WriterAgent works with dreaming_enabled=False (default)."""
        # Write router config first
        (tmp_path / "model_router.json").write_text(
            json.dumps(
                {
                    "model_tier": "test",
                    "tier_defaults": {"test": {"anthropic": "claude-haiku-4-5-20251001"}},
                }
            )
        )

        layout = ProjectLayout(series_root=tmp_path, book_id="test-book")
        spec_loader = SpecLoader(workspace_root=tmp_path)
        ledger_manager = LedgerManager(book_id="test-book", data_root=tmp_path)

        ctx = AgentContext(
            project_layout=layout,
            spec_loader=spec_loader,
            ledger_manager=ledger_manager,
            log_path=tmp_path / "agent.log",
            output_dir=tmp_path / "output",
        )

        router = ModelRouter(
            config_path=tmp_path / "model_router.json",
            cost_log_path=tmp_path / "cost.jsonl",
        )

        agent = WriterAgent(ctx, router)

        assert agent._memory_path is None  # No memory file when disabled

    def test_writer_agent_with_dreaming_enabled(self, tmp_path: Path) -> None:
        """WriterAgent loads persistent memory when dreaming_enabled=True."""
        # Write router config first
        (tmp_path / "model_router.json").write_text(
            json.dumps(
                {
                    "model_tier": "test",
                    "tier_defaults": {"test": {"anthropic": "claude-haiku-4-5-20251001"}},
                }
            )
        )

        layout = ProjectLayout(series_root=tmp_path, book_id="test-book")
        spec_loader = SpecLoader(workspace_root=tmp_path)
        ledger_manager = LedgerManager(book_id="test-book", data_root=tmp_path)

        memory_path = tmp_path / "agent_memory"
        config = ManagedAgentConfig(
            managed_agent_mode=True,
            persistent_memory_path=memory_path,
            dreaming_enabled=True,
        )

        ctx = AgentContext(
            project_layout=layout,
            spec_loader=spec_loader,
            ledger_manager=ledger_manager,
            log_path=tmp_path / "agent.log",
            output_dir=tmp_path / "output",
            managed_agent_config=config,
        )

        router = ModelRouter(
            config_path=tmp_path / "model_router.json",
            cost_log_path=tmp_path / "cost.jsonl",
        )

        agent = WriterAgent(ctx, router)

        assert agent._memory_path is not None
        assert agent._memory_path == memory_path / "WriterAgent.memory.json"

    def test_writer_agent_memory_persistence(self, tmp_path: Path) -> None:
        """WriterAgent saves memory after successful generation."""
        layout = ProjectLayout(series_root=tmp_path, book_id="test-book")
        spec_loader = SpecLoader(workspace_root=tmp_path)
        ledger_manager = LedgerManager(book_id="test-book", data_root=tmp_path)

        memory_path = tmp_path / "agent_memory"
        config = ManagedAgentConfig(
            managed_agent_mode=True,
            persistent_memory_path=memory_path,
            dreaming_enabled=True,
        )

        ctx = AgentContext(
            project_layout=layout,
            spec_loader=spec_loader,
            ledger_manager=ledger_manager,
            log_path=tmp_path / "agent.log",
            output_dir=tmp_path / "output",
            managed_agent_config=config,
        )

        router = Mock(spec=ModelRouter)

        agent = WriterAgent(ctx, router)

        # Simulate successful output
        output = WriterOutput(
            draft_text="Test scene prose here.",
            word_count=4,
            scene_id="scene_01",
        )

        agent._update_memory_from_output(output, "scene_01")

        # Verify memory file created
        memory_file = memory_path / "WriterAgent.memory.json"
        assert memory_file.exists()

        memory = json.loads(memory_file.read_text())
        assert memory["scenes_completed"] == 1
        assert memory["total_words_generated"] == 4
        assert len(memory["successful_scenes"]) == 1
        assert memory["successful_scenes"][0]["scene_id"] == "scene_01"

    def test_writer_agent_memory_load(self, tmp_path: Path) -> None:
        """WriterAgent loads existing memory file."""
        layout = ProjectLayout(series_root=tmp_path, book_id="test-book")
        spec_loader = SpecLoader(workspace_root=tmp_path)
        ledger_manager = LedgerManager(book_id="test-book", data_root=tmp_path)

        memory_path = tmp_path / "agent_memory"
        memory_path.mkdir(parents=True, exist_ok=True)

        # Pre-seed memory
        existing_memory = {
            "scenes_completed": 5,
            "total_words_generated": 5000,
            "successful_scenes": [
                {"scene_id": "scene_01", "word_count": 1000},
            ],
        }
        memory_file = memory_path / "WriterAgent.memory.json"
        memory_file.write_text(json.dumps(existing_memory))

        config = ManagedAgentConfig(
            managed_agent_mode=True,
            persistent_memory_path=memory_path,
            dreaming_enabled=True,
        )

        ctx = AgentContext(
            project_layout=layout,
            spec_loader=spec_loader,
            ledger_manager=ledger_manager,
            log_path=tmp_path / "agent.log",
            output_dir=tmp_path / "output",
            managed_agent_config=config,
        )

        router = Mock(spec=ModelRouter)
        agent = WriterAgent(ctx, router)

        loaded_memory = agent._load_memory()

        assert loaded_memory["scenes_completed"] == 5
        assert loaded_memory["total_words_generated"] == 5000
