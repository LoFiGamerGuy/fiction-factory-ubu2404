"""ContextPackBuilder — materialises per-scene per-agent context packs with provenance.

Per the MBSE Agent Views pattern: every agent call has a materialised JSON
record at a canonical path, with a companion provenance.json that contains
the SHA-256 hash of the context content.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline.core.context_manager import ContextBundle
from pipeline.core.project_layout import ProjectLayout

logger = logging.getLogger(__name__)

VIEW_SCHEMA_VERSION = "1.0"


@dataclass
class ContextPack:
    """Materialised context record for one agent-call in the pipeline."""

    agent_id: str
    scene_id: str
    job_id: str
    generated_at: str
    view_schema_version: str
    context_tiers: dict[str, str]  # {scene, book, series}
    author_dashboard_summary: dict[str, Any]
    source_file_hashes: dict[str, str]
    provenance_hash: str
    output_path: Path = field(default_factory=lambda: Path("."))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["output_path"] = str(d["output_path"])
        return d


class ContextPackBuilder:
    """Builds and writes ContextPacks with provenance JSON.

    Every pack is written to ``ProjectLayout.context_pack_path(agent_id, scene_id)``.
    A companion ``provenance.json`` is written alongside each pack.
    """

    def __init__(self, project_layout: ProjectLayout) -> None:
        self._layout = project_layout

    def build(
        self,
        job_id: str,
        agent_id: str,
        scene_id: str,
        context_bundle: ContextBundle,
        source_files: list[Path] | None = None,
    ) -> ContextPack:
        """Build and write a ContextPack for one agent/scene pair.

        ``source_files`` are the files read during context assembly; their
        SHA-256 hashes are recorded in provenance. Pass an empty list or None
        if no files were read.
        """
        generated_at = datetime.now(UTC).isoformat()
        source_file_hashes = _hash_files(source_files or [])
        context_tiers = context_bundle.as_tiers_dict()
        provenance_hash = _compute_provenance_hash(
            context_tiers=context_tiers,
            source_file_hashes=source_file_hashes,
            view_schema_version=VIEW_SCHEMA_VERSION,
            agent_id=agent_id,
            scene_id=scene_id,
        )

        output_path = self._layout.context_pack_path(agent_id, scene_id)

        pack = ContextPack(
            agent_id=agent_id,
            scene_id=scene_id,
            job_id=job_id,
            generated_at=generated_at,
            view_schema_version=VIEW_SCHEMA_VERSION,
            context_tiers=context_tiers,
            author_dashboard_summary=context_bundle.author_dashboard_summary,
            source_file_hashes=source_file_hashes,
            provenance_hash=provenance_hash,
            output_path=output_path,
        )

        self._write(pack)
        return pack

    # ── I/O ───────────────────────────────────────────────────────────────────

    def _write(self, pack: ContextPack) -> None:
        pack.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Main pack JSON
        with pack.output_path.open("w", encoding="utf-8") as fh:
            json.dump(pack.to_dict(), fh, indent=2, default=str)

        # Companion provenance.json
        prov_path = self._layout.provenance_path(pack.agent_id, pack.scene_id)
        provenance_record = {
            "agent_id": pack.agent_id,
            "scene_id": pack.scene_id,
            "job_id": pack.job_id,
            "generated_at": pack.generated_at,
            "view_schema_version": pack.view_schema_version,
            "source_file_hashes": pack.source_file_hashes,
            "provenance_hash": pack.provenance_hash,
        }
        prov_path.parent.mkdir(parents=True, exist_ok=True)
        with prov_path.open("w", encoding="utf-8") as fh:
            json.dump(provenance_record, fh, indent=2)

        logger.debug("ContextPack written: %s", pack.output_path)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _hash_files(paths: list[Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in paths:
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result[str(path)] = digest
        except OSError as exc:
            logger.warning("Could not hash file %s: %s", path, exc)
            result[str(path)] = "unreadable"
    return result


def _compute_provenance_hash(
    *,
    context_tiers: dict[str, str],
    source_file_hashes: dict[str, str],
    view_schema_version: str,
    agent_id: str,
    scene_id: str,
) -> str:
    payload = json.dumps(
        {
            "context_tiers": context_tiers,
            "source_file_hashes": source_file_hashes,
            "view_schema_version": view_schema_version,
            "agent_id": agent_id,
            "scene_id": scene_id,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
