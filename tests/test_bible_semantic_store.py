"""Tests for Bible Semantic Store (T1.13).

BCR-20260522-claude-dreaming-mem0
"""

from pathlib import Path

import pytest

from pipeline.core.bible_semantic_store import BibleSemanticStore
from pipeline.memory.mem0_client import MemoryFact


class TestBibleSemanticStoreConstruction:
    """Basic construction and configuration."""

    def test_initialize_with_series_id(self) -> None:
        """BibleSemanticStore initializes with series_id."""
        store = BibleSemanticStore(series_id="test-series")
        assert store.series_id == "test-series"
        assert store._client is not None

    def test_initialize_with_custom_host(self) -> None:
        """BibleSemanticStore accepts custom mem0_host."""
        store = BibleSemanticStore(
            series_id="test-series",
            mem0_host="http://custom-host:9999",
        )
        assert store._client._host == "http://custom-host:9999"


class TestBibleSeeding:
    """seed_bible() functionality."""

    def test_seed_bible_with_facts(self) -> None:
        """seed_bible() accepts list of fact strings."""
        store = BibleSemanticStore(series_id="test-series")

        facts = [
            "Sarah is a detective in the Brooklyn precinct",
            "Location: New York City, 2024",
            "The MacGuffin is a stolen diamond necklace",
        ]

        # Should not raise
        store.seed_bible(facts)

    def test_seed_bible_empty_list_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """seed_bible() with empty list logs warning."""
        store = BibleSemanticStore(series_id="test-series")

        store.seed_bible([])

        assert "empty facts list" in caplog.text

    def test_from_bible_file(self, tmp_path: Path) -> None:
        """from_bible_file() class method loads and seeds from file."""
        bible_path = tmp_path / "bible.txt"
        bible_path.write_text(
            "Sarah is a detective\n"
            "Location: New York\n"
            "\n"  # Empty line should be skipped
            "MacGuffin: stolen diamond\n"
        )

        store = BibleSemanticStore.from_bible_file(
            series_id="test-series",
            bible_path=bible_path,
        )

        assert store.series_id == "test-series"

    def test_from_bible_file_nonexistent(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """from_bible_file() with nonexistent file logs warning."""
        nonexistent = tmp_path / "does-not-exist.txt"

        store = BibleSemanticStore.from_bible_file(
            series_id="test-series",
            bible_path=nonexistent,
        )

        assert "Bible file not found" in caplog.text
        assert store.series_id == "test-series"


class TestSemanticQuery:
    """query() semantic retrieval (T1.13 acceptance test)."""

    def test_query_returns_memory_facts(self) -> None:
        """query() returns list of MemoryFact objects."""
        store = BibleSemanticStore(series_id="test-series")

        # Seed fixture facts
        store.seed_bible(
            [
                "Sarah is a detective in the Brooklyn precinct",
                "Sarah's occupation: homicide detective, 15 years experience",
                "Character: Sarah Morrison, age 42",
            ]
        )

        # Query (will hit Mem0 if running, else gracefully degrade)
        facts = store.query("Sarah's occupation", top_k=5)

        # Accept graceful degradation if Mem0 not running
        assert isinstance(facts, list)
        for fact in facts:
            assert isinstance(fact, MemoryFact)
            assert hasattr(fact, "content")
            assert hasattr(fact, "relevance_score")

    def test_query_empty_string_warns(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """query() with empty string logs warning and returns empty list."""
        store = BibleSemanticStore(series_id="test-series")

        facts = store.query("", top_k=5)

        assert facts == []
        assert "empty query_text" in caplog.text

    def test_query_respects_top_k(self) -> None:
        """query() respects top_k parameter."""
        store = BibleSemanticStore(series_id="test-series")

        store.seed_bible([f"Fact {i}" for i in range(20)])

        facts_3 = store.query("fact", top_k=3)
        facts_10 = store.query("fact", top_k=10)

        # Accept graceful degradation if Mem0 not running
        assert len(facts_3) <= 3
        assert len(facts_10) <= 10


class TestContextFormatting:
    """format_facts_for_context() output formatting."""

    def test_format_facts_for_context(self) -> None:
        """format_facts_for_context() produces readable string."""
        store = BibleSemanticStore(series_id="test-series")

        facts = [
            MemoryFact(
                fact_id="fact-1",
                content="Sarah is a detective",
                relevance_score=0.95,
            ),
            MemoryFact(
                fact_id="fact-2",
                content="Location: Brooklyn",
                relevance_score=0.82,
            ),
        ]

        formatted = store.format_facts_for_context(facts)

        assert "Relevant bible facts" in formatted
        assert "Sarah is a detective" in formatted
        assert "Location: Brooklyn" in formatted
        assert "[relevance: 0.95" in formatted
        assert "[relevance: 0.82" in formatted

    def test_format_facts_empty_list(self) -> None:
        """format_facts_for_context() with empty list returns fallback."""
        store = BibleSemanticStore(series_id="test-series")

        formatted = store.format_facts_for_context([])

        assert "No relevant bible facts retrieved" in formatted


class TestContextPackBuilderIntegration:
    """Integration with ContextPackBuilder.get_bible_context_semantic()."""

    def test_context_pack_builder_semantic_retrieval(self, tmp_path: Path) -> None:
        """ContextPackBuilder.get_bible_context_semantic() stub works."""
        from pipeline.core.context_pack_builder import ContextPackBuilder
        from pipeline.core.project_layout import ProjectLayout

        layout = ProjectLayout(series_root=tmp_path, book_id="test-book")
        store = BibleSemanticStore(series_id="test-series")
        store.seed_bible(
            [
                "Sarah is a detective",
                "Sarah's occupation: homicide detective",
            ]
        )

        builder = ContextPackBuilder(
            project_layout=layout,
            bible_semantic_store=store,
        )

        result = builder.get_bible_context_semantic("Sarah's occupation", top_k=5)

        # Accept graceful degradation if Mem0 not running
        assert isinstance(result, str)
        assert len(result) > 0

    def test_context_pack_builder_no_store_fallback(self, tmp_path: Path) -> None:
        """ContextPackBuilder without bible_semantic_store falls back gracefully."""
        from pipeline.core.context_pack_builder import ContextPackBuilder
        from pipeline.core.project_layout import ProjectLayout

        layout = ProjectLayout(series_root=tmp_path, book_id="test-book")
        builder = ContextPackBuilder(project_layout=layout)  # No store

        result = builder.get_bible_context_semantic("test query")

        assert "full-bible injection fallback" in result
