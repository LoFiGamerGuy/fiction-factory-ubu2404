"""Unit tests — Author Dashboard API (Task 013).

Tests:
  1. test_status_no_run          — GET /runs/{run_id}/status when no state file exists
  2. test_ledgers_endpoint       — GET /books/{book_id}/ledgers with mocked LedgerManager
  3. test_metrics_history_empty  — GET /books/{book_id}/metrics/history with no data file
  4. test_series_promises_empty  — GET /series/{series_id}/promises with no data file
  5. test_evoskill_empty         — GET /series/{series_id}/evoskill with no skills dir
  6. test_book_summary_empty     — GET /books/{book_id}/summary with no summary file
  7. test_quality_gates_empty    — GET /books/{book_id}/quality_gates with no history file
  8. test_sse_route_registered   — /runs/{run_id}/stream route is registered in the app
"""

from __future__ import annotations

import dataclasses
import json
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
from pipeline.ledgers.intimacy_escalation_ledger import IntimacyEscalationLedger, IntimacyEvent
from pipeline.ledgers.promise_ledger import PromiseEvent, PromiseLedger
from pipeline.ledgers.series_promise_ledger import SeriesPromiseEvent, SeriesPromiseLedger

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


def test_status_no_run(dashboard_data_root: Path) -> None:
    """When no run_state.json exists, endpoint returns sentinel with run_id."""
    response = client.get("/runs/test_run/status")

    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["status"] == "no_active_run"


def test_status_reads_run_state(dashboard_data_root: Path) -> None:
    """Run status endpoint reads persisted state from configured data root."""
    run_dir = dashboard_data_root / "job-123"
    run_dir.mkdir(parents=True)
    (run_dir / "run_state.json").write_text(
        '{"run_id": "job-123", "status": "completed", "active_scene": "scene-01"}',
        encoding="utf-8",
    )

    response = client.get("/runs/job-123/status")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["active_scene"] == "scene-01"


def test_status_reads_environment_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runtime dashboard can point at a generated run through FF_DASHBOARD_DATA_ROOT."""
    previous = getattr(app.state, "data_root", _MISSING)
    if previous is not _MISSING:
        del app.state.data_root
    monkeypatch.setenv("FF_DASHBOARD_DATA_ROOT", str(tmp_path))
    run_dir = tmp_path / "job-env"
    run_dir.mkdir(parents=True)
    (run_dir / "run_state.json").write_text(
        '{"run_id": "job-env", "status": "completed", "active_scene": "scene-env"}',
        encoding="utf-8",
    )
    try:
        response = client.get("/runs/job-env/status")
    finally:
        if previous is not _MISSING:
            app.state.data_root = previous

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["active_scene"] == "scene-env"


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


def test_metrics_history_beat_fallback_from_sqlite(dashboard_data_root: Path) -> None:
    """Beat granularity returns scene-backed fallback points until beat events exist."""
    book_id = "book-api-beats"
    _append_metrics_event(
        dashboard_data_root,
        book_id,
        chapter_id="chapter-01",
        scene_id="scene-01",
        word_count=1000,
        interiority_pct=0.20,
    )

    response = client.get(
        f"/books/{book_id}/metrics/history?granularity=beat&metric=interiority_pct"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["granularity"] == "beat"
    assert body["items"][0]["beat_id"] == "scene-01"
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


def test_series_promises_empty(dashboard_data_root: Path) -> None:
    """When series_promises.jsonl doesn't exist, endpoint returns empty dict."""
    response = client.get("/series/series-xyz/promises")

    assert response.status_code == 200
    assert response.json() == {}


def test_book_promises_reads_sqlite(dashboard_data_root: Path) -> None:
    """Book promise endpoint returns PromiseLedger events grouped by promise_id."""
    book_id = "book-api-promises"
    ledger = PromiseLedger(book_id, data_root=dashboard_data_root)
    ledger.append(
        PromiseEvent(
            event_id=_uid(),
            book_id=book_id,
            promise_id="promise-1",
            timestamp=_now(),
            event_type="opened",
            promise_type="romantic_tension",
            scene_id="scene-01",
            priority="high",
            description="Emma and Marcus must resolve the cafe renovation conflict.",
        )
    )
    ledger.close()

    response = client.get(f"/books/{book_id}/promises")

    assert response.status_code == 200
    body = response.json()
    assert body["book_id"] == book_id
    assert body["promises"]["promise-1"][0]["event_type"] == "opened"


def test_book_intimacy_reads_sqlite(dashboard_data_root: Path) -> None:
    """Intimacy endpoint returns IntimacyEscalationLedger events in append order."""
    book_id = "book-api-intimacy"
    ledger = IntimacyEscalationLedger(book_id, data_root=dashboard_data_root)
    ledger.append(
        IntimacyEvent(
            event_id=_uid(),
            book_id=book_id,
            scene_id="scene-02",
            pair_id="emma-marcus",
            character_pair=["emma", "marcus"],
            chapter_number=1,
            timestamp=_now(),
            event_type="first_touch",
            heat_level="sensual",
            description="Their hands brush while reaching for the same wrench.",
            consent_present=True,
        )
    )
    ledger.close()

    response = client.get(f"/books/{book_id}/intimacy")

    assert response.status_code == 200
    body = response.json()
    assert body["book_id"] == book_id
    assert body["events"][0]["pair_id"] == "emma-marcus"
    assert body["events"][0]["event_type"] == "first_touch"


def test_series_promises_reads_sqlite(dashboard_data_root: Path) -> None:
    """Series promise endpoint reads the SQLite SeriesPromiseLedger used by runtime."""
    series_id = "series-api-promises"
    ledger = SeriesPromiseLedger(series_id, data_root=dashboard_data_root)
    ledger.append(
        SeriesPromiseEvent(
            event_id=_uid(),
            series_id=series_id,
            book_id="book-01",
            scene_id="scene-01",
            promise_id="series-promise-1",
            timestamp=_now(),
            promise_type="series_thread",
            status="opened",
            description="The waterfront redevelopment threat continues across books.",
            book_number=1,
            opened_book=1,
            must_resolve_by_book=3,
        )
    )
    ledger.close()

    response = client.get(f"/series/{series_id}/promises")

    assert response.status_code == 200
    body = response.json()
    assert body["series-promise-1"][0]["status"] == "opened"
    assert body["series-promise-1"][0]["must_resolve_by_book"] == 3


def test_evoskill_empty(dashboard_data_root: Path) -> None:
    """When the skills directory doesn't exist, endpoint returns empty list."""
    response = client.get("/series/series-xyz/evoskill")

    assert response.status_code == 200
    assert response.json() == []


def test_voice_calibration_reads_series_profile(dashboard_data_root: Path) -> None:
    """Voice calibration endpoint resolves run-local series voice profile YAML."""
    series_id = "series-api-voice"
    profile_dir = dashboard_data_root.parent / "series" / series_id / "profiles"
    profile_dir.mkdir(parents=True)
    (profile_dir / "voice_profile.yaml").write_text(
        "profile_id: voice-fixture\n"
        "version: '1.2'\n"
        "display_name: Fixture Voice\n"
        "calibration_history:\n"
        "  - run_id: calibration-001\n"
        "    timestamp: 2026-06-11T00:00:00+00:00\n"
        "    voice_fidelity_distance: 0.12\n",
        encoding="utf-8",
    )

    response = client.get(f"/series/{series_id}/voice_calibration")

    assert response.status_code == 200
    body = response.json()
    assert body["profile_found"] is True
    assert body["profile_id"] == "voice-fixture"
    assert body["calibration_history"][0]["run_id"] == "calibration-001"


def test_book_summary_empty(dashboard_data_root: Path) -> None:
    """When book_run_summary.json doesn't exist, endpoint returns a disabled sentinel."""
    response = client.get("/books/book-xyz/summary")

    assert response.status_code == 200
    assert response.json() == {
        "book_id": "book-xyz",
        "summary_found": False,
        "word_budget_status": {"enabled": False},
    }


def test_book_summary_reads_books_dir(dashboard_data_root: Path) -> None:
    """Summary endpoint reads book_run_summary.json below the configured data root."""
    book_dir = dashboard_data_root / "books" / "book-xyz"
    book_dir.mkdir(parents=True)
    payload = {
        "book_id": "book-xyz",
        "run_id": "run-123",
        "word_budget_status": {
            "enabled": True,
            "book_word_count_target": 4600,
            "planned_word_count_target": 5400,
            "actual_word_count": 4614,
            "remaining_word_budget": -14,
            "projected_final_count": 4614,
            "min_scene_target": 250,
            "scenes": [
                {
                    "scene_id": "ch01_sc01",
                    "planned_word_count_target": 450,
                    "adjusted_word_count_target": 383,
                    "actual_word_count": 390,
                    "projected_final_count_after": 4680,
                }
            ],
        },
    }
    (book_dir / "book_run_summary.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    response = client.get("/books/book-xyz/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["summary_found"] is True
    assert body["run_id"] == "run-123"
    assert body["word_budget_status"]["actual_word_count"] == 4614
    assert body["word_budget_status"]["scenes"][0]["adjusted_word_count_target"] == 383


def test_book_summary_finds_acceptance_series_path(dashboard_data_root: Path) -> None:
    """Dashboard data roots can resolve summaries in sibling acceptance series output."""
    data_root = dashboard_data_root / "acceptance-run" / "data"
    app.state.data_root = data_root
    summary_dir = (
        data_root.parent / "series" / "book-acceptance-series" / "data" / "books" / "book-xyz"
    )
    summary_dir.mkdir(parents=True)
    (summary_dir / "book_run_summary.json").write_text(
        json.dumps(
            {
                "book_id": "book-xyz",
                "word_budget_status": {
                    "enabled": True,
                    "book_word_count_target": 4600,
                    "actual_word_count": 4403,
                },
            }
        ),
        encoding="utf-8",
    )

    response = client.get("/books/book-xyz/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["summary_found"] is True
    assert body["word_budget_status"]["book_word_count_target"] == 4600
    assert body["summary_path"].endswith("book_run_summary.json")


def test_quality_gates_empty(dashboard_data_root: Path) -> None:
    """When quality_gate_history.jsonl doesn't exist, endpoint returns empty list."""
    response = client.get("/books/book-xyz/quality_gates")

    assert response.status_code == 200
    assert response.json() == []


def test_quality_gates_reads_data_root(dashboard_data_root: Path) -> None:
    """Quality gate endpoint reads persisted events from configured data root."""
    book_dir = dashboard_data_root / "book-xyz"
    book_dir.mkdir(parents=True)
    (book_dir / "quality_gate_history.jsonl").write_text(
        '{"event": "run_finished", "scene_id": "scene-01", "decision": "GO"}\n',
        encoding="utf-8",
    )

    response = client.get("/books/book-xyz/quality_gates")

    assert response.status_code == 200
    assert response.json() == [{"event": "run_finished", "scene_id": "scene-01", "decision": "GO"}]


def test_sse_route_registered() -> None:
    """The SSE stream route is registered in the FastAPI app at the expected path."""
    api_routes = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/runs/{run_id}/stream" in api_routes
