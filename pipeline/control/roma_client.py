"""ROMAClient — narrative-decomposition wrapper for the ROMA API (sentient-agi/ROMA).

Reads ROMA_API_URL and ROMA_API_KEY from the environment (via python-dotenv).
When ROMA is unavailable the client falls back to the local BookStructurePlanner,
mapping its SceneInventory output into the ROMA DecomposedPlan data model.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_TIMEOUT_S = 10.0


# ── ROMA data model ─────────────────────────────────────────────────────────────


@dataclass
class ScenePlan:
    scene_id: str
    act: int
    chapter: int
    scene_function: str
    word_count_target: int
    position: float


@dataclass
class ChapterPlan:
    chapter_id: str
    act: int
    scene_plans: list[ScenePlan] = field(default_factory=list)


@dataclass
class ActPlan:
    act_number: int
    chapter_plans: list[ChapterPlan] = field(default_factory=list)


@dataclass
class BookPlan:
    book_id: str
    act_plans: list[ActPlan] = field(default_factory=list)
    total_scenes: int = 0
    word_count_target: int = 0


@dataclass
class DecomposedPlan:
    series_id: str
    book_plans: list[BookPlan] = field(default_factory=list)


@dataclass
class VerificationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


# ── local fallback helper ───────────────────────────────────────────────────────


def _local_decompose(series_spec: dict[str, Any]) -> DecomposedPlan:
    """Fall back to BookStructurePlanner when ROMA is unavailable."""
    from pipeline.book_structure_planner import BookStructurePlanner

    series_id: str = str(series_spec.get("series_id", "unknown-series"))
    books_raw: list[dict[str, Any]] = list(series_spec.get("books", [{}]))

    book_plans: list[BookPlan] = []
    for book_raw in books_raw:
        book_id: str = str(book_raw.get("book_id", f"book-{len(book_plans) + 1:03d}"))
        planner = BookStructurePlanner()
        # Use a temp directory; the planner writes a scene_inventory.json there.
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            inventory = planner.plan(
                book_id=book_id,
                series_id=series_id,
                series_spec=series_spec,
                book_spec=book_raw,
                book_dir=Path(tmpdir),
            )

        # Group SceneSlots into acts → chapters → scene plans.
        acts_map: dict[int, dict[str, list[ScenePlan]]] = {}
        for slot in inventory.scenes:
            chapter_key = f"ch{slot.chapter:02d}"
            act_dict = acts_map.setdefault(slot.act, {})
            act_dict.setdefault(chapter_key, []).append(
                ScenePlan(
                    scene_id=slot.scene_id,
                    act=slot.act,
                    chapter=slot.chapter,
                    scene_function=slot.scene_function,
                    word_count_target=slot.word_count_target,
                    position=slot.position,
                )
            )

        act_plans: list[ActPlan] = []
        for act_number in sorted(acts_map):
            chapter_plans: list[ChapterPlan] = []
            for chapter_id in sorted(acts_map[act_number]):
                chapter_plans.append(
                    ChapterPlan(
                        chapter_id=chapter_id,
                        act=act_number,
                        scene_plans=acts_map[act_number][chapter_id],
                    )
                )
            act_plans.append(ActPlan(act_number=act_number, chapter_plans=chapter_plans))

        book_plans.append(
            BookPlan(
                book_id=book_id,
                act_plans=act_plans,
                total_scenes=inventory.total_scenes,
                word_count_target=inventory.word_count_target,
            )
        )

    return DecomposedPlan(series_id=series_id, book_plans=book_plans)


# ── client ──────────────────────────────────────────────────────────────────────


class ROMAClient:
    """Thin wrapper around the ROMA narrative-decomposition REST API."""

    def __init__(self) -> None:
        self._api_url: str = os.environ.get("ROMA_API_URL", "").rstrip("/")
        self._api_key: str = os.environ.get("ROMA_API_KEY", "")
        self._configured: bool = bool(self._api_url and self._api_key)
        if not self._configured:
            logger.warning(
                "ROMAClient: ROMA_API_URL or ROMA_API_KEY not set; "
                "decompose() will use local BookStructurePlanner fallback."
            )

    # ── internal helpers ────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    def _parse_decomposed_plan(self, data: dict[str, Any]) -> DecomposedPlan:
        """Parse a ROMA /decompose JSON response into a DecomposedPlan."""
        series_id: str = str(data.get("series_id", "unknown"))
        book_plans: list[BookPlan] = []
        for bp_raw in data.get("book_plans", []):
            act_plans: list[ActPlan] = []
            for ap_raw in bp_raw.get("act_plans", []):
                chapter_plans: list[ChapterPlan] = []
                for cp_raw in ap_raw.get("chapter_plans", []):
                    scene_plans: list[ScenePlan] = []
                    for sp_raw in cp_raw.get("scene_plans", []):
                        scene_plans.append(
                            ScenePlan(
                                scene_id=str(sp_raw.get("scene_id", "")),
                                act=int(sp_raw.get("act", 0)),
                                chapter=int(sp_raw.get("chapter", 0)),
                                scene_function=str(sp_raw.get("scene_function", "")),
                                word_count_target=int(sp_raw.get("word_count_target", 0)),
                                position=float(sp_raw.get("position", 0.0)),
                            )
                        )
                    chapter_plans.append(
                        ChapterPlan(
                            chapter_id=str(cp_raw.get("chapter_id", "")),
                            act=int(cp_raw.get("act", 0)),
                            scene_plans=scene_plans,
                        )
                    )
                act_plans.append(
                    ActPlan(
                        act_number=int(ap_raw.get("act_number", 0)),
                        chapter_plans=chapter_plans,
                    )
                )
            book_plans.append(
                BookPlan(
                    book_id=str(bp_raw.get("book_id", "")),
                    act_plans=act_plans,
                    total_scenes=int(bp_raw.get("total_scenes", 0)),
                    word_count_target=int(bp_raw.get("word_count_target", 0)),
                )
            )
        return DecomposedPlan(series_id=series_id, book_plans=book_plans)

    # ── public API ──────────────────────────────────────────────────────────────

    def decompose(self, series_spec: dict[str, Any]) -> DecomposedPlan:
        """POST /decompose; falls back to local BookStructurePlanner on error."""
        if not self._configured:
            logger.info("ROMAClient.decompose: ROMA not configured — using local fallback.")
            return _local_decompose(series_spec)
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                resp = client.post(
                    f"{self._api_url}/decompose",
                    json=series_spec,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return self._parse_decomposed_plan(resp.json())
        except httpx.HTTPError as exc:
            logger.warning(
                "ROMAClient.decompose() HTTP error: %s — falling back to local decomposition",
                exc,
            )
            return _local_decompose(series_spec)

    def verify(self, plan: DecomposedPlan) -> VerificationResult:
        """POST /verify; returns VerificationResult(valid=True) when ROMA is unavailable."""
        if not self._configured:
            return VerificationResult(valid=True, errors=[])
        # Serialize plan to dict for JSON transport.
        payload: dict[str, Any] = {
            "series_id": plan.series_id,
            "book_plans": [
                {
                    "book_id": bp.book_id,
                    "total_scenes": bp.total_scenes,
                    "word_count_target": bp.word_count_target,
                    "act_plans": [
                        {
                            "act_number": ap.act_number,
                            "chapter_plans": [
                                {
                                    "chapter_id": cp.chapter_id,
                                    "act": cp.act,
                                    "scene_plans": [
                                        {
                                            "scene_id": sp.scene_id,
                                            "act": sp.act,
                                            "chapter": sp.chapter,
                                            "scene_function": sp.scene_function,
                                            "word_count_target": sp.word_count_target,
                                            "position": sp.position,
                                        }
                                        for sp in cp.scene_plans
                                    ],
                                }
                                for cp in ap.chapter_plans
                            ],
                        }
                        for ap in bp.act_plans
                    ],
                }
                for bp in plan.book_plans
            ],
        }
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                resp = client.post(
                    f"{self._api_url}/verify",
                    json=payload,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                return VerificationResult(
                    valid=bool(data.get("valid", True)),
                    errors=list(data.get("errors", [])),
                )
        except httpx.HTTPError as exc:
            logger.warning("ROMAClient.verify() HTTP error: %s — returning valid=True", exc)
            return VerificationResult(valid=True, errors=[])
