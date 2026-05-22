"""Bible Semantic Store — Mem0-backed semantic retrieval for series continuity.

Wraps Mem0Client to provide bible-specific semantic search. Reduces context
bloat from full-bible injection by retrieving only top-K relevant facts per query.

By book 3 of a series, bible could be 50K+ tokens. Semantic retrieval (top-5
facts) vs full injection saves 90%+ tokens.

BCR-20260522-claude-dreaming-mem0 (T1.13)
"""

from __future__ import annotations

import logging
from pathlib import Path

from pipeline.memory.mem0_client import Mem0Client, MemoryFact

logger = logging.getLogger(__name__)


class BibleSemanticStore:
    """Semantic retrieval over series bible via Mem0.

    Usage:
        store = BibleSemanticStore(series_id="my-series")
        store.seed_bible(["Sarah is a detective", "Location: New York, 2024"])
        facts = store.query("Sarah's occupation", top_k=5)
    """

    def __init__(
        self,
        series_id: str,
        mem0_host: str | None = None,
    ) -> None:
        """Initialize bible semantic store.

        Args:
            series_id: Unique series identifier (for Mem0 metadata filtering)
            mem0_host: Mem0 server URL (defaults to localhost:8888 or MEM0_HOST env var)
        """
        self.series_id = series_id
        self._client = Mem0Client(host=mem0_host)
        logger.info("BibleSemanticStore initialized for series=%s", series_id)

    def seed_bible(self, facts: list[str]) -> None:
        """Seed bible facts into Mem0 at series init.

        Args:
            facts: List of fact strings (e.g., character descriptions, world rules)
        """
        if not facts:
            logger.warning("seed_bible called with empty facts list")
            return

        logger.info("Seeding %d bible facts for series=%s", len(facts), self.series_id)
        self._client.seed_series(self.series_id, facts)

    def query(
        self,
        query_text: str,
        top_k: int = 5,
    ) -> list[MemoryFact]:
        """Semantic search for relevant bible facts.

        Args:
            query_text: Natural language query (e.g., "Sarah's occupation")
            top_k: Number of top results to return (default: 5 per T014-003)

        Returns:
            List of MemoryFact objects sorted by relevance score (descending)
        """
        if not query_text.strip():
            logger.warning("query called with empty query_text")
            return []

        logger.debug(
            "BibleSemanticStore query: series=%s, query=%r, top_k=%d",
            self.series_id,
            query_text,
            top_k,
        )

        facts = self._client.retrieve(
            query=query_text,
            series_id=self.series_id,
            n=top_k,
        )

        logger.debug("Retrieved %d facts (requested top_k=%d)", len(facts), top_k)
        return facts

    def format_facts_for_context(self, facts: list[MemoryFact]) -> str:
        """Format retrieved facts as a context string for agent injection.

        Args:
            facts: List of MemoryFact objects from query()

        Returns:
            Formatted string for context pack injection
        """
        if not facts:
            return "(No relevant bible facts retrieved)"

        lines = ["Relevant bible facts (semantic retrieval):"]
        for i, fact in enumerate(facts, 1):
            lines.append(f"  {i}. {fact.content} [relevance: {fact.relevance_score:.3f}]")

        return "\n".join(lines)

    @classmethod
    def from_bible_file(
        cls,
        series_id: str,
        bible_path: Path,
        mem0_host: str | None = None,
    ) -> BibleSemanticStore:
        """Initialize and seed from a bible text file.

        Args:
            series_id: Unique series identifier
            bible_path: Path to bible text file (one fact per line)
            mem0_host: Mem0 server URL (optional)

        Returns:
            Initialized BibleSemanticStore with seeded facts
        """
        store = cls(series_id=series_id, mem0_host=mem0_host)

        if not bible_path.exists():
            logger.warning("Bible file not found: %s", bible_path)
            return store

        facts = [line.strip() for line in bible_path.read_text().splitlines() if line.strip()]
        store.seed_bible(facts)

        return store
