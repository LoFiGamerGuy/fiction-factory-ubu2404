"""Mem0Client — semantic bible retrieval via self-hosted Mem0."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "http://localhost:8888"


@dataclass
class MemoryFact:
    fact_id: str
    content: str
    relevance_score: float


class Mem0Client:
    """Semantic memory retrieval via a self-hosted Mem0 instance.

    Degrades gracefully: if Mem0 is unreachable or not installed, all methods
    become no-ops / return empty results. A single warning is logged at init.
    """

    def __init__(self, host: str | None = None) -> None:
        self._host = host or os.environ.get("MEM0_HOST", _DEFAULT_HOST)
        self._available = False
        self._client: object | None = None

        try:
            import mem0  # noqa: PLC0415

            self._client = mem0.MemoryClient(host=self._host)
            self._available = True
            logger.debug("Mem0Client connected to %s", self._host)
        except ImportError:
            logger.warning("mem0ai not installed — Mem0Client running in degraded (no-op) mode.")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Mem0Client could not connect to %s (%s) — running in degraded mode.",
                self._host,
                exc,
            )

    # ── Public API ─────────────────────────────────────────────────────────────

    def seed_series(self, series_id: str, content_items: list[str]) -> None:
        """Add content items to Mem0 tagged with series_id metadata.

        No-op if Mem0 is unavailable.
        """
        if not self._available or self._client is None:
            return
        for item in content_items:
            try:
                self._client.add(  # type: ignore[attr-defined]
                    item,
                    metadata={"series_id": series_id},
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Mem0Client.seed_series add failed: %s", exc)

    def retrieve(
        self,
        query: str,
        series_id: str,
        n: int = 5,
    ) -> list[MemoryFact]:
        """Semantic search over series memory.

        Returns top-n MemoryFacts sorted by relevance. Returns empty list if
        Mem0 is unavailable.
        """
        if not self._available or self._client is None:
            return []
        try:
            results = self._client.search(  # type: ignore[attr-defined]
                query,
                metadata={"series_id": series_id},
                limit=n,
            )
            facts: list[MemoryFact] = []
            for r in results:
                facts.append(
                    MemoryFact(
                        fact_id=str(r.get("id", "")),
                        content=str(r.get("memory", r.get("content", ""))),
                        relevance_score=float(r.get("score", 0.0)),
                    )
                )
            return facts
        except Exception as exc:  # noqa: BLE001
            logger.warning("Mem0Client.retrieve failed: %s", exc)
            return []
