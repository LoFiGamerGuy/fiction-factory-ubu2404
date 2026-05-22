"""AgentContext — shared dependency container for all pipeline agents.

Every agent constructor takes a single AgentContext. This is the fail-fast
pattern (DEC-008): AgentContext raises ValueError at construction if any
required field is missing, so agents never silently run with incomplete deps.

BCR-20260522: Added managed_agent_config for Claude Managed Agents support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.core.managed_agent_config import ManagedAgentConfig
from pipeline.ledgers.ledger_manager import LedgerManager
from pipeline.profiles.spec_loader import SpecLoader


@dataclass
class AgentContext:
    """Shared dependencies injected into every pipeline agent.

    ``voice_exemplar_manager`` is reserved for Phase 8 (VoiceExemplarManager).
    Set to None in all Phase 6 constructions; Phase 8 populates it without
    changing this constructor signature.

    ``managed_agent_config`` added in BCR-20260522 for Claude Managed Agents
    (persistent memory, Files API, Message Batches API, Dreaming).
    """

    project_layout: Any  # ProjectLayout — Any to avoid circular import at module level
    spec_loader: SpecLoader
    ledger_manager: LedgerManager
    log_path: Path
    output_dir: Path
    model_tier: str = "test"
    voice_exemplar_manager: Any = field(default=None)  # Phase 8: VoiceExemplarManager
    managed_agent_config: ManagedAgentConfig = field(default_factory=ManagedAgentConfig)

    def __post_init__(self) -> None:
        missing: list[str] = []
        if self.project_layout is None:
            missing.append("project_layout")
        if self.spec_loader is None:
            missing.append("spec_loader")
        if self.ledger_manager is None:
            missing.append("ledger_manager")
        if self.log_path is None:
            missing.append("log_path")
        if self.output_dir is None:
            missing.append("output_dir")
        if missing:
            raise ValueError(f"AgentContext missing required field(s): {', '.join(missing)}")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
