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
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


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


def test_metrics_history_empty() -> None:
    """When book_metrics.jsonl doesn't exist, endpoint returns empty dict."""
    with patch("api.main.Path") as mock_path_cls:
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        # Path("data") / book_id / "book_metrics.jsonl"
        mock_path_cls.return_value.__truediv__ = lambda self, other: mock_file

        response = client.get("/books/book-xyz/metrics/history")

    assert response.status_code == 200
    assert response.json() == {}


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
