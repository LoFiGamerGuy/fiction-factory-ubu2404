"""Shared helpers for Phase 8 specialist agents."""

from __future__ import annotations

import json
import logging
from typing import Any

from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext

logger = logging.getLogger(__name__)


def scene_text(job_context: JobContext) -> str:
    """Return the best available scene prose from accumulated agent output."""
    for agent_id, field_name in (
        ("editor_agent", "edited_text"),
        ("line_editor_agent", "polished_text"),
        ("copy_editor_agent", "corrected_text"),
        ("proofreader_agent", "proofread_text"),
        ("writer_agent", "draft_text"),
    ):
        data = job_context.output_data.get(agent_id, {})
        if isinstance(data, dict):
            text = data.get(field_name, "")
            if isinstance(text, str) and text:
                return text
    return job_context.final_text


def load_memory(ctx: AgentContext, agent_name: str) -> dict[str, Any]:
    """Load Dreaming memory for an agent, or an empty dict when disabled/missing."""
    if not ctx.managed_agent_config or not ctx.managed_agent_config.dreaming_enabled:
        return {}

    memory_file = ctx.managed_agent_config.get_memory_file(agent_name)
    if not memory_file.exists():
        logger.debug("%s: no persistent memory found (first run)", agent_name)
        return {}

    try:
        data: dict[str, Any] = json.loads(memory_file.read_text(encoding="utf-8"))
        logger.info(
            "%s: loaded memory (scenes_checked=%d)", agent_name, data.get("scenes_checked", 0)
        )
        return data
    except Exception as exc:
        logger.warning("%s: failed to load memory: %s", agent_name, exc)
        return {}


def save_memory(ctx: AgentContext, agent_name: str, scene_id: str, payload: dict[str, Any]) -> None:
    """Append compact Dreaming memory for an agent when enabled."""
    if not ctx.managed_agent_config or not ctx.managed_agent_config.dreaming_enabled:
        return

    memory_file = ctx.managed_agent_config.get_memory_file(agent_name)
    memory_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        existing: dict[str, Any] = {}
        if memory_file.exists():
            existing = json.loads(memory_file.read_text(encoding="utf-8"))

        existing["scenes_checked"] = existing.get("scenes_checked", 0) + 1
        recent = existing.setdefault("recent_scenes", [])
        recent.append({"scene_id": scene_id, **payload})
        existing["recent_scenes"] = recent[-10:]
        memory_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        logger.debug("%s: saved memory (%d scenes)", agent_name, existing["scenes_checked"])
    except Exception as exc:
        logger.warning("%s: failed to save memory: %s", agent_name, exc)
