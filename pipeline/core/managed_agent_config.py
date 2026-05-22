"""Claude Managed Agents configuration for persistent memory and Dreaming.

Provides infrastructure for:
- Persistent memory (filesystem-backed notes across sessions)
- Files API preparation (hooks for Phase 6 bible/profile uploads)
- Message Batches API support (hooks for Phase 14 bulk operations)
- Dreaming evaluation (real-time agent reflection vs EvoSkill nightly pass)

BCR-20260522-claude-dreaming-mem0 (T1.12)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ManagedAgentConfig:
    """Configuration for Claude Managed Agents features.

    Attributes:
        managed_agent_mode: Enable Claude persistent memory and Dreaming features
        persistent_memory_path: Directory for agent session notes (filesystem-backed)
        files_api_enabled: Enable Files API for bible/profile uploads (Phase 6+)
        message_batches_enabled: Enable Message Batches API for bulk ops (Phase 14+)
        dreaming_enabled: Enable real-time agent reflection (vs EvoSkill nightly)
    """

    managed_agent_mode: bool = False
    persistent_memory_path: Path | None = None
    files_api_enabled: bool = False
    message_batches_enabled: bool = False
    dreaming_enabled: bool = False

    # Files API state (populated in Phase 6)
    uploaded_file_ids: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate configuration consistency."""
        if self.managed_agent_mode:
            if self.persistent_memory_path is None:
                raise ValueError("managed_agent_mode=True requires persistent_memory_path")
            if not isinstance(self.persistent_memory_path, Path):
                self.persistent_memory_path = Path(self.persistent_memory_path)
            self.persistent_memory_path.mkdir(parents=True, exist_ok=True)

        # Dreaming requires managed agent mode
        if self.dreaming_enabled and not self.managed_agent_mode:
            raise ValueError("dreaming_enabled=True requires managed_agent_mode=True")

    def get_memory_file(self, agent_id: str) -> Path:
        """Get persistent memory file path for an agent.

        Args:
            agent_id: Unique agent identifier (e.g., "WriterAgent")

        Returns:
            Path to agent's persistent memory notes file

        Raises:
            ValueError: If managed_agent_mode is False
        """
        if not self.managed_agent_mode or self.persistent_memory_path is None:
            raise ValueError("get_memory_file() requires managed_agent_mode=True")
        return self.persistent_memory_path / f"{agent_id}.memory.json"

    def register_uploaded_file(self, key: str, file_id: str) -> None:
        """Register a file uploaded via Files API.

        Args:
            key: Logical name (e.g., "series_bible", "voice_profile")
            file_id: Claude file ID from upload response
        """
        if not self.files_api_enabled:
            raise ValueError("register_uploaded_file() requires files_api_enabled=True")
        self.uploaded_file_ids[key] = file_id

    def get_file_id(self, key: str) -> str | None:
        """Retrieve uploaded file ID by logical key.

        Args:
            key: Logical name registered via register_uploaded_file()

        Returns:
            File ID if found, None otherwise
        """
        return self.uploaded_file_ids.get(key)
