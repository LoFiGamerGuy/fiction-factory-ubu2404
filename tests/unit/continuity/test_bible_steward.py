"""Unit tests for BibleSteward (Task 009)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.continuity.bible_steward import BibleSteward
from pipeline.continuity.bible_types import (
    BibleDelta,
    BibleEntity,
    BibleState,
)


def _make_delta(
    entity_id: str = "char_alice",
    entity_type: str = "character",
    operation: str = "upsert",
    new_attributes: dict[str, Any] | None = None,
    **kwargs: Any,
) -> BibleDelta:
    return BibleDelta(
        delta_id="d001",
        entity_id=entity_id,
        entity_type=entity_type,
        operation=operation,
        new_attributes=new_attributes or {},
        **kwargs,
    )


class TestValidateDeltaTypeMismatch:
    def test_type_mismatch_detected(self, tmp_path: Path) -> None:
        steward = BibleSteward(tmp_path / "bible")
        state = BibleState(
            entities={
                "char_alice": BibleEntity(
                    entity_id="char_alice",
                    entity_type="character",
                    attributes={},
                )
            }
        )
        delta = _make_delta(entity_id="char_alice", entity_type="location")
        proposed = steward.propose_delta(delta)
        result = steward.validate_delta(proposed, state)
        assert not result.valid
        assert result.contradiction_type == "type_mismatch"

    def test_same_type_passes(self, tmp_path: Path) -> None:
        steward = BibleSteward(tmp_path / "bible")
        state = BibleState(
            entities={
                "char_alice": BibleEntity(
                    entity_id="char_alice",
                    entity_type="character",
                    attributes={},
                )
            }
        )
        delta = _make_delta(entity_id="char_alice", entity_type="character")
        proposed = steward.propose_delta(delta)
        result = steward.validate_delta(proposed, state)
        assert result.valid


class TestValidateDeltaTimeline:
    def test_duplicate_timestamp_raises(self, tmp_path: Path) -> None:
        steward = BibleSteward(tmp_path / "bible")
        state = BibleState(
            timeline_events=[{"entity_id": "char_alice", "timestamp": "2023-01-01T10:00:00"}]
        )
        delta = BibleDelta(
            delta_id="d002",
            entity_id="char_alice",
            entity_type="character",
            operation="append_timeline",
            timeline_event={"entity_id": "char_alice", "timestamp": "2023-01-01T10:00:00"},
        )
        proposed = steward.propose_delta(delta)
        result = steward.validate_delta(proposed, state)
        assert not result.valid
        assert result.contradiction_type == "timeline_violation"

    def test_new_timestamp_passes(self, tmp_path: Path) -> None:
        steward = BibleSteward(tmp_path / "bible")
        state = BibleState(
            timeline_events=[{"entity_id": "char_alice", "timestamp": "2023-01-01T10:00:00"}]
        )
        delta = BibleDelta(
            delta_id="d003",
            entity_id="char_alice",
            entity_type="character",
            operation="append_timeline",
            timeline_event={"entity_id": "char_alice", "timestamp": "2023-01-02T10:00:00"},
        )
        proposed = steward.propose_delta(delta)
        result = steward.validate_delta(proposed, state)
        assert result.valid


class TestCommitDeltaAtomic:
    def test_commit_creates_bible_file(self, tmp_path: Path) -> None:
        steward = BibleSteward(tmp_path / "bible")
        delta = _make_delta(new_attributes={"current_location": "Thornfield"})
        proposed = steward.propose_delta(delta)
        steward.commit_delta(proposed, book_id="book1")

        bible_path = tmp_path / "bible" / "book1" / "bible.json"
        assert bible_path.exists()

    def test_commit_creates_event_log(self, tmp_path: Path) -> None:
        steward = BibleSteward(tmp_path / "bible")
        delta = _make_delta(new_attributes={"role": "protagonist"})
        proposed = steward.propose_delta(delta)
        steward.commit_delta(proposed, book_id="book1")

        log_path = tmp_path / "bible" / "book1" / "bible_events.jsonl"
        assert log_path.exists()
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_commit_creates_snapshot(self, tmp_path: Path) -> None:
        steward = BibleSteward(tmp_path / "bible")
        delta = _make_delta(new_attributes={"role": "protagonist"})
        proposed = steward.propose_delta(delta)
        steward.commit_delta(proposed, book_id="book1")

        snapshots = list((tmp_path / "bible" / "book1" / "snapshots").glob("*.json"))
        assert len(snapshots) == 1

    def test_query_after_commit(self, tmp_path: Path) -> None:
        steward = BibleSteward(tmp_path / "bible")
        delta = _make_delta(
            entity_id="char_alice",
            entity_type="character",
            new_attributes={"current_location": "Thornfield"},
        )
        proposed = steward.propose_delta(delta)
        steward.commit_delta(proposed, book_id="book1")

        entity = steward.query("char_alice", "book1")
        assert entity is not None
        assert entity.entity_id == "char_alice"
        assert entity.attributes["current_location"] == "Thornfield"

    def test_commit_syncs_character_card_to_wuphf(self, tmp_path: Path) -> None:
        calls: list[dict[str, str]] = []

        class FakeWUPHF:
            def update_wiki(self, page: str, content: str, author: str = "pipeline") -> None:
                calls.append({"page": page, "content": content, "author": author})

        steward = BibleSteward(
            tmp_path / "bible",
            wuphf_client=FakeWUPHF(),
            series_id="series1",
        )
        delta = _make_delta(
            entity_id="char_alice",
            entity_type="character",
            new_attributes={"current_location": "Thornfield"},
            source_scene_id="ch01_sc01",
        )

        steward.commit_delta(steward.propose_delta(delta), book_id="book1")

        assert calls == [
            {
                "page": "series-bible/series1/characters/char_alice",
                "content": (
                    "# char_alice\n\n"
                    "Entity type: `character`\n\n"
                    "Book: `book1`\n\n"
                    "Source scene: `ch01_sc01`\n\n"
                    "Operation: `upsert`\n\n"
                    "Status: `active`\n\n"
                    "## Attributes\n\n"
                    "```json\n"
                    '{\n  "current_location": "Thornfield"\n}\n'
                    "```\n"
                ),
                "author": "bible_steward",
            }
        ]


class TestHashChain:
    def test_hash_changes_across_commits(self, tmp_path: Path) -> None:
        steward = BibleSteward(tmp_path / "bible")
        import json

        d1 = _make_delta(entity_id="char_alice", new_attributes={"role": "protagonist"})
        steward.commit_delta(steward.propose_delta(d1), book_id="book1")

        d2 = _make_delta(entity_id="char_bob", new_attributes={"role": "antagonist"})
        steward.commit_delta(steward.propose_delta(d2), book_id="book1")

        log_path = tmp_path / "bible" / "book1" / "bible_events.jsonl"
        events = [json.loads(line) for line in log_path.read_text().splitlines()]
        assert len(events) == 2
        hash1 = events[0]["content_hash"]
        hash2 = events[1]["content_hash"]
        assert hash1 != hash2

    def test_prev_hash_chained(self, tmp_path: Path) -> None:
        steward = BibleSteward(tmp_path / "bible")
        import json

        d1 = _make_delta(entity_id="char_alice", new_attributes={"role": "protagonist"})
        steward.commit_delta(steward.propose_delta(d1), book_id="book1")
        d2 = _make_delta(entity_id="char_bob", new_attributes={"role": "antagonist"})
        steward.commit_delta(steward.propose_delta(d2), book_id="book1")

        log_path = tmp_path / "bible" / "book1" / "bible_events.jsonl"
        events = [json.loads(line) for line in log_path.read_text().splitlines()]
        assert events[1]["prev_hash"] == events[0]["content_hash"]
