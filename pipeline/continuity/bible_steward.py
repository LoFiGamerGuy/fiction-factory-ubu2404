"""BibleSteward — atomic bible delta management with content-hash chain.

Safety properties:
  - commit_delta: atomic os.replace() + exclusive file lock; no partial writes.
  - Append-only event log (bible_events.jsonl).
  - Content-hash chain: each event includes previous event's hash.
  - Per-commit snapshot.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline.continuity.bible_types import (
    BibleDelta,
    BibleEntity,
    BibleState,
    ProposedDelta,
    ValidationResult,
)

logger = logging.getLogger(__name__)

_CONTRADICTION_TYPES = frozenset(
    {"type_mismatch", "timeline_violation", "spatial", "capability", "voice", "taboo"}
)


class BibleSteward:
    """Manages the series/book bible with atomic writes and contradiction detection."""

    def __init__(
        self,
        bible_dir: Path,
        wuphf_client: Any | None = None,
        series_id: str | None = None,
    ) -> None:
        self._dir = bible_dir
        self._wuphf = wuphf_client
        self._series_id = series_id
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── Paths ─────────────────────────────────────────────────────────────────

    def _bible_path(self, book_id: str) -> Path:
        return self._dir / book_id / "bible.json"

    def _event_log_path(self, book_id: str) -> Path:
        return self._dir / book_id / "bible_events.jsonl"

    def _snapshot_dir(self, book_id: str) -> Path:
        return self._dir / book_id / "snapshots"

    # ── Public API ─────────────────────────────────────────────────────────────

    def propose_delta(self, delta: BibleDelta) -> ProposedDelta:
        """Validate delta structure; return ProposedDelta with generated ID."""
        if not delta.entity_id:
            raise ValueError("delta.entity_id must not be empty")
        if not delta.operation:
            raise ValueError("delta.operation must not be empty")
        return ProposedDelta(original=delta, proposed_id=str(uuid.uuid4())[:8])

    def validate_delta(self, delta: ProposedDelta, current_bible: BibleState) -> ValidationResult:
        """Check delta against all 6 contradiction types."""
        d = delta.original
        existing = current_bible.entity(d.entity_id)

        # 1. type_mismatch: existing entity has different type
        if existing and existing.entity_type != d.entity_type:
            return ValidationResult(
                valid=False,
                contradiction_type="type_mismatch",
                detail=(
                    f"Entity '{d.entity_id}' already exists as type "
                    f"'{existing.entity_type}'; delta says '{d.entity_type}'."
                ),
            )

        # 2. timeline_violation: event timestamp conflicts
        if d.operation == "append_timeline" and d.timeline_event:
            result = self._check_timeline(d, current_bible)
            if not result.valid:
                return result

        # 3. spatial: character in conflicting location
        if d.entity_type == "character" and existing:
            result = self._check_spatial(d, existing)
            if not result.valid:
                return result

        # 4. capability: action contradicts established capability
        if d.entity_type == "character" and existing:
            result = self._check_capability(d, existing)
            if not result.valid:
                return result

        # 5. voice: behavior violates voice signature
        if d.entity_type == "character" and existing:
            result = self._check_voice(d, existing)
            if not result.valid:
                return result

        # 6. taboo: content prohibited by sensitivity profile
        result = self._check_taboo(d)
        if not result.valid:
            return result

        return ValidationResult(valid=True)

    def commit_delta(self, delta: ProposedDelta, book_id: str) -> None:
        """Atomically commit delta: lock → apply → hash → os.replace → log → snapshot."""
        bible_path = self._bible_path(book_id)
        bible_path.parent.mkdir(parents=True, exist_ok=True)

        lock_path = bible_path.parent / ".bible.lock"
        lock_path.touch(exist_ok=True)
        committed_state: BibleState | None = None

        with lock_path.open("r") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                state = self._load_state(book_id)
                self._apply_delta(delta.original, state)

                bible_json = json.dumps(
                    {
                        "entities": {
                            eid: {
                                "entity_id": e.entity_id,
                                "entity_type": e.entity_type,
                                "attributes": e.attributes,
                            }
                            for eid, e in state.entities.items()
                        },
                        "timeline_events": state.timeline_events,
                    },
                    sort_keys=True,
                )

                prev_hash = state.content_hash
                new_hash = hashlib.sha256((prev_hash + bible_json).encode()).hexdigest()[:16]

                # Atomic write
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    dir=bible_path.parent,
                    delete=False,
                    suffix=".tmp",
                    encoding="utf-8",
                ) as tmp:
                    tmp.write(bible_json)
                    tmp_path = Path(tmp.name)
                os.replace(tmp_path, bible_path)

                # Append to event log
                event: dict[str, Any] = {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "proposed_id": delta.proposed_id,
                    "entity_id": delta.original.entity_id,
                    "operation": delta.original.operation,
                    "content_hash": new_hash,
                    "prev_hash": prev_hash,
                    "source_scene_id": delta.original.source_scene_id,
                }
                with self._event_log_path(book_id).open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event) + "\n")

                # Snapshot
                snap_n = len(list(self._snapshot_dir(book_id).glob("*.json")))
                self._snapshot_dir(book_id).mkdir(parents=True, exist_ok=True)
                snap_path = self._snapshot_dir(book_id) / f"bible_snapshot_{snap_n:04d}.json"
                snap_path.write_text(bible_json, encoding="utf-8")

                committed_state = state
                logger.debug("BibleSteward: committed %s hash=%s", delta.proposed_id, new_hash)
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

        if committed_state is not None:
            self._sync_wuphf_wiki(delta, book_id, committed_state)

    def query(self, entity_id: str, book_id: str) -> BibleEntity | None:
        """Return an entity from the current bible, or None if not found."""
        state = self._load_state(book_id)
        return state.entity(entity_id)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _load_state(self, book_id: str) -> BibleState:
        bible_path = self._bible_path(book_id)
        if not bible_path.exists():
            return BibleState()
        try:
            data: dict[str, Any] = json.loads(bible_path.read_text(encoding="utf-8"))
            entities: dict[str, BibleEntity] = {}
            for eid, e in data.get("entities", {}).items():
                entities[eid] = BibleEntity(
                    entity_id=e["entity_id"],
                    entity_type=e["entity_type"],
                    attributes=e.get("attributes", {}),
                )
            # Restore content_hash from the last event log entry
            content_hash = self._last_event_hash(book_id)
            return BibleState(
                entities=entities,
                timeline_events=data.get("timeline_events", []),
                content_hash=content_hash,
            )
        except Exception:
            return BibleState()

    def _last_event_hash(self, book_id: str) -> str:
        """Return the content_hash from the most recent event log entry, or ''."""
        log_path = self._event_log_path(book_id)
        if not log_path.exists():
            return ""
        try:
            lines = log_path.read_text(encoding="utf-8").strip().splitlines()
            if not lines:
                return ""
            last = json.loads(lines[-1])
            return str(last.get("content_hash", ""))
        except Exception:
            return ""

    def _sync_wuphf_wiki(
        self,
        delta: ProposedDelta,
        book_id: str,
        state: BibleState,
    ) -> None:
        """Best-effort sync of committed bible entities to the WUPHF series-bible wiki."""
        if self._wuphf is None:
            return
        try:
            page = self._wiki_page_for_delta(delta.original)
            markdown = self._render_entity_markdown(delta.original, book_id, state)
            self._wuphf.update_wiki(page, markdown, author="bible_steward")
        except Exception as exc:
            logger.warning(
                "BibleSteward: WUPHF wiki sync failed for %s: %s",
                delta.original.entity_id,
                exc,
            )

    def _wiki_page_for_delta(self, delta: BibleDelta) -> str:
        prefix = "series-bible"
        if self._series_id:
            prefix = f"{prefix}/{self._series_id}"
        if delta.entity_type == "character":
            return f"{prefix}/characters/{delta.entity_id}"
        return f"{prefix}/world-facts/{delta.entity_type}/{delta.entity_id}"

    @staticmethod
    def _render_entity_markdown(delta: BibleDelta, book_id: str, state: BibleState) -> str:
        entity = state.entity(delta.entity_id)
        attributes = entity.attributes if entity is not None else delta.new_attributes
        status = "deleted" if delta.operation == "delete" else "active"
        return (
            f"# {delta.entity_id}\n\n"
            f"Entity type: `{delta.entity_type}`\n\n"
            f"Book: `{book_id}`\n\n"
            f"Source scene: `{delta.source_scene_id or 'unknown'}`\n\n"
            f"Operation: `{delta.operation}`\n\n"
            f"Status: `{status}`\n\n"
            "## Attributes\n\n"
            "```json\n"
            f"{json.dumps(attributes, indent=2, sort_keys=True)}\n"
            "```\n"
        )

    @staticmethod
    def _apply_delta(delta: BibleDelta, state: BibleState) -> None:
        if delta.operation in ("upsert", "append_timeline"):
            if delta.operation == "upsert":
                state.entities[delta.entity_id] = BibleEntity(
                    entity_id=delta.entity_id,
                    entity_type=delta.entity_type,
                    attributes=delta.new_attributes,
                )
            if delta.timeline_event:
                state.timeline_events.append(delta.timeline_event)
        elif delta.operation == "delete":
            state.entities.pop(delta.entity_id, None)

    @staticmethod
    def _check_timeline(delta: BibleDelta, state: BibleState) -> ValidationResult:
        event = delta.timeline_event
        if event is None:
            return ValidationResult(valid=True)
        ts = event.get("timestamp")
        if ts is None:
            return ValidationResult(valid=True)
        for existing_event in state.timeline_events:
            if (
                existing_event.get("entity_id") == delta.entity_id
                and existing_event.get("timestamp") == ts
            ):
                return ValidationResult(
                    valid=False,
                    contradiction_type="timeline_violation",
                    detail=f"Event at timestamp '{ts}' already exists for '{delta.entity_id}'.",
                )
        return ValidationResult(valid=True)

    @staticmethod
    def _check_spatial(delta: BibleDelta, existing: BibleEntity) -> ValidationResult:
        new_location = delta.new_attributes.get("current_location")
        forbidden = existing.attributes.get("cannot_be_at", [])
        if new_location and isinstance(forbidden, list) and new_location in forbidden:
            return ValidationResult(
                valid=False,
                contradiction_type="spatial",
                detail=(
                    f"'{delta.entity_id}' cannot be at '{new_location}' "
                    f"(established spatial constraint)."
                ),
            )
        return ValidationResult(valid=True)

    @staticmethod
    def _check_capability(delta: BibleDelta, existing: BibleEntity) -> ValidationResult:
        new_action = delta.new_attributes.get("action")
        incapabilities = existing.attributes.get("cannot_do", [])
        if new_action and isinstance(incapabilities, list) and new_action in incapabilities:
            return ValidationResult(
                valid=False,
                contradiction_type="capability",
                detail=(
                    f"'{delta.entity_id}' cannot perform '{new_action}' "
                    f"(established capability constraint)."
                ),
            )
        return ValidationResult(valid=True)

    @staticmethod
    def _check_voice(delta: BibleDelta, existing: BibleEntity) -> ValidationResult:
        new_phrase = delta.new_attributes.get("dialogue_sample", "")
        forbidden_phrases = existing.attributes.get("voice_forbidden_phrases", [])
        if isinstance(forbidden_phrases, list):
            for fp in forbidden_phrases:
                if fp and fp.lower() in new_phrase.lower():
                    return ValidationResult(
                        valid=False,
                        contradiction_type="voice",
                        detail=(f"'{delta.entity_id}' dialogue contains forbidden phrase '{fp}'."),
                    )
        return ValidationResult(valid=True)

    @staticmethod
    def _check_taboo(delta: BibleDelta) -> ValidationResult:
        taboo_marker = delta.new_attributes.get("_taboo_violation")
        if taboo_marker:
            return ValidationResult(
                valid=False,
                contradiction_type="taboo",
                detail=f"Delta flagged with taboo violation: {taboo_marker}",
            )
        return ValidationResult(valid=True)
