"""Unit tests — Author Dashboard API (Task 013).

Tests:
  1. test_status_no_run          — GET /runs/{run_id}/status when no state file exists
  2. test_ledgers_endpoint       — GET /books/{book_id}/ledgers with mocked LedgerManager
  3. test_metrics_history_empty  — GET /books/{book_id}/metrics/history with no data file
  4. test_series_promises_empty  — GET /series/{series_id}/promises with no data file
  5. test_evoskill_empty         — GET /series/{series_id}/evoskill with no skills dir
  6. test_quality_gates_empty    — GET /books/{book_id}/quality_gates with no history file
  7. test_sse_route_registered   — /runs/{run_id}/stream route is registered in the app
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from api.main import app
from pipeline.ledgers.book_metrics_ledger import BookMetricsEvent, BookMetricsLedger

client = TestClient(app)
_MISSING = object()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_dummy_dashboard(book_id: str = "book-test") -> Any:
    """Return a minimal AuthorDashboard-compatible dataclass instance."""
    from pipeline.ledgers.ledger_manager import AuthorDashboard

    return AuthorDashboard(
        book_id=book_id,
        scene_id="current",
        word_count_total=1000,
        interiority_pct_running=0.25,
        dialogue_ratio_running=0.40,
        ai_tell_count_total=2,
        sex_scene_count=1,
        character_arcs={"alice": "midpoint"},
        intimacy_pairs={"alice-bob": "kiss"},
        reader_info_known=5,
        reader_info_unknown=2,
        reader_info_active_irony=1,
        subplots_open=3,
        subplots_resolved=1,
        trope_beats_pending=2,
        trope_beats_overdue=0,
        series_promises_open=1,
        scene_rhythm=["action", "dialogue"],
        promises_open=4,
        promises_critical_open=1,
        bible_unresolved_contradictions=0,
    )


@pytest.fixture
def dashboard_data_root(tmp_path: Path) -> Iterator[Path]:
    previous = getattr(app.state, "data_root", _MISSING)
    app.state.data_root = tmp_path
    yield tmp_path
    if previous is _MISSING:
        del app.state.data_root
    else:
        app.state.data_root = previous


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _append_metrics_event(
    data_root: Path,
    book_id: str,
    *,
    chapter_id: str,
    scene_id: str,
    word_count: int,
    interiority_pct: float,
    character_metrics: dict[str, Any] | None = None,
) -> None:
    ledger = BookMetricsLedger(book_id, data_root=data_root)
    ledger.append(
        BookMetricsEvent(
            event_id=_uid(),
            book_id=book_id,
            chapter_id=chapter_id,
            scene_id=scene_id,
            timestamp=_now(),
            word_count=word_count,
            interiority_pct=interiority_pct,
            dialogue_ratio=0.40,
            exposition_pct=0.15,
            action_pct=0.10,
            sensory_density_per_1k=8.0,
            em_dash_density=3.0,
            sentence_length_avg=14.0,
            ai_tell_count=1,
            no_fly_violations=0,
            heat_curve_position=0.2,
            sex_scene_flag=False,
            character_metrics=character_metrics or {},
        )
    )
    ledger.close()


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_status_no_run() -> None:
    """When no run_state.json exists, endpoint returns sentinel with run_id."""
    with patch("api.main.Path") as mock_path_cls:
        # Make the state file appear to not exist.
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = lambda self, other: mock_path_instance
        mock_path_instance.exists.return_value = False
        mock_path_cls.return_value = mock_path_instance

        response = client.get("/runs/test_run/status")

    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data


def test_ledgers_endpoint() -> None:
    """LedgerManager is mocked; response is 200 and contains book_id."""
    dummy = _make_dummy_dashboard("book-abc")

    mock_manager = MagicMock()
    mock_manager.get_dashboard_summary.return_value = dummy

    with patch("pipeline.ledgers.ledger_manager.LedgerManager", return_value=mock_manager):
        # Patch the import *inside* the endpoint function.
        with patch("api.main.dataclasses") as mock_dc:
            mock_dc.asdict.return_value = dataclasses.asdict(dummy)
            with patch.dict(
                "sys.modules",
                {
                    "pipeline.ledgers.ledger_manager": MagicMock(
                        LedgerManager=MagicMock(return_value=mock_manager)
                    )
                },
            ):
                response = client.get("/books/book-abc/ledgers")

    # Even if the import inside the endpoint goes to the real module, the
    # LedgerManager constructor is mocked so no disk I/O happens.
    assert response.status_code == 200
    body = response.json()
    assert "book_id" in body


def test_metrics_history_empty(dashboard_data_root: Path) -> None:
    """When no SQLite book metrics events exist, endpoint returns an empty items list."""
    response = client.get("/books/book-xyz/metrics/history")

    assert response.status_code == 200
    assert response.json() == {
        "book_id": "book-xyz",
        "granularity": "chapter",
        "metric": None,
        "items": [],
    }


def test_metrics_history_scene_from_sqlite(dashboard_data_root: Path) -> None:
    """Scene history comes from the SQLite BookMetricsLedger, not jsonl files."""
    book_id = "book-api-scenes"
    _append_metrics_event(
        dashboard_data_root,
        book_id,
        chapter_id="chapter-01",
        scene_id="scene-01",
        word_count=1000,
        interiority_pct=0.20,
    )
    _append_metrics_event(
        dashboard_data_root,
        book_id,
        chapter_id="chapter-01",
        scene_id="scene-02",
        word_count=3000,
        interiority_pct=0.40,
    )

    response = client.get(
        f"/books/{book_id}/metrics/history?granularity=scene&metric=interiority_pct"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["book_id"] == book_id
    assert body["granularity"] == "scene"
    assert body["metric"] == "interiority_pct"
    assert [item["scene_id"] for item in body["items"]] == ["scene-01", "scene-02"]
    assert body["items"][0]["metrics"] == {"interiority_pct": 0.20}


def test_character_metrics_endpoint_from_sqlite(dashboard_data_root: Path) -> None:
    """Character metrics endpoint returns only scenes containing that character."""
    book_id = "book-api-characters"
    _append_metrics_event(
        dashboard_data_root,
        book_id,
        chapter_id="chapter-01",
        scene_id="scene-01",
        word_count=1000,
        interiority_pct=0.25,
        character_metrics={"sarah": {"mtld": 72.5, "question_rate": 0.10}},
    )
    _append_metrics_event(
        dashboard_data_root,
        book_id,
        chapter_id="chapter-01",
        scene_id="scene-02",
        word_count=900,
        interiority_pct=0.30,
        character_metrics={"miles": {"mtld": 64.0}},
    )

    response = client.get(f"/books/{book_id}/characters/sarah/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "book_id": book_id,
        "character_id": "sarah",
        "items": [
            {
                "event_id": body["items"][0]["event_id"],
                "book_id": book_id,
                "chapter_id": "chapter-01",
                "scene_id": "scene-01",
                "timestamp": body["items"][0]["timestamp"],
                "metrics": {"mtld": 72.5, "question_rate": 0.10},
            }
        ],
    }


def test_series_promises_empty() -> None:
    """When series_promises.jsonl doesn't exist, endpoint returns empty dict."""
    with patch("api.main.Path") as mock_path_cls:
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_path_cls.return_value.__truediv__ = lambda self, other: mock_file

        response = client.get("/series/series-xyz/promises")

    assert response.status_code == 200
    assert response.json() == {}


def test_evoskill_empty() -> None:
    """When the skills directory doesn't exist, endpoint returns empty list."""
    with patch("api.main.Path") as mock_path_cls:
        mock_dir = MagicMock()
        mock_dir.exists.return_value = False
        mock_path_cls.return_value.__truediv__ = lambda self, other: mock_dir

        response = client.get("/series/series-xyz/evoskill")

    assert response.status_code == 200
    assert response.json() == []


def test_quality_gates_empty() -> None:
    """When quality_gate_history.jsonl doesn't exist, endpoint returns empty list."""
    with patch("api.main.Path") as mock_path_cls:
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_path_cls.return_value.__truediv__ = lambda self, other: mock_file

        response = client.get("/books/book-xyz/quality_gates")

    assert response.status_code == 200
    assert response.json() == []


def test_sse_route_registered() -> None:
    """The SSE stream route is registered in the FastAPI app at the expected path."""
    api_routes = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/runs/{run_id}/stream" in api_routes
