"""Integration tests — Control + Collaboration Layer (Task 011).

All HTTP calls are mocked via unittest.mock.patch; no real network requests
are made.  Tests run without any real Paperclip / WUPHF / ROMA instances.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_control_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all control-plane env vars before each test to avoid bleed-over."""
    for var in (
        "PAPERCLIP_API_URL",
        "PAPERCLIP_API_KEY",
        "WUPHF_API_URL",
        "WUPHF_API_KEY",
        "ROMA_API_URL",
        "ROMA_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def paperclip_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set Paperclip env vars to fixture values."""
    monkeypatch.setenv("PAPERCLIP_API_URL", "http://paperclip.test/api/v1")
    monkeypatch.setenv("PAPERCLIP_API_KEY", "pk_test_abc123")


@pytest.fixture()
def wuphf_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set WUPHF env vars to fixture values."""
    monkeypatch.setenv("WUPHF_API_URL", "http://wuphf.test/api/v1")
    monkeypatch.setenv("WUPHF_API_KEY", "wk_test_abc123")


@pytest.fixture()
def roma_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set ROMA env vars to fixture values."""
    monkeypatch.setenv("ROMA_API_URL", "http://roma.test/api/v1")
    monkeypatch.setenv("ROMA_API_KEY", "rk_test_abc123")


# ── helper: build a minimal mock httpx response ───────────────────────────────


def _mock_response(
    status_code: int = 200,
    json_body: Any = None,
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    resp.raise_for_status.return_value = None  # no-op for 2xx
    return resp


# ── Paperclip tests ───────────────────────────────────────────────────────────


class TestPaperclipCheckBudgetNoEnv:
    """1. PaperclipClient with no env vars returns True (graceful degradation)."""

    def test_paperclip_check_budget_no_env(self) -> None:
        # Import after env is cleared by the autouse fixture.
        from pipeline.control.paperclip_client import PaperclipClient

        client = PaperclipClient()
        result = client.check_budget("writer")
        assert result is True


class TestPaperclipRecordCostMocked:
    """2. record_cost makes a POST to /costs with correct args."""

    def test_paperclip_record_cost_mocked(self, paperclip_env: None) -> None:
        from pipeline.control.paperclip_client import PaperclipClient

        mock_resp = _mock_response(200, {})

        with patch("pipeline.control.paperclip_client.httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_ctx
            mock_ctx.post.return_value = mock_resp

            client = PaperclipClient()
            client.record_cost("writer", 0.05, tokens_used=1500)

            mock_ctx.post.assert_called_once_with(
                "http://paperclip.test/api/v1/costs",
                json={"agent_role": "writer", "cost_usd": 0.05, "tokens_used": 1500},
                headers={
                    "Authorization": "Bearer pk_test_abc123",
                    "Content-Type": "application/json",
                },
            )


class TestPaperclipRequestApprovalImmediate:
    """3. request_approval returns True when the first poll returns 'approved'."""

    def test_paperclip_request_approval_immediate(self, paperclip_env: None) -> None:
        from pipeline.control.paperclip_client import PaperclipClient

        post_resp = _mock_response(200, {"approval_id": "appr-001"})
        poll_resp = _mock_response(200, {"status": "approved"})

        with patch("pipeline.control.paperclip_client.httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_ctx
            # First call = POST /approvals, second = GET /approvals/{id}
            mock_ctx.post.return_value = post_resp
            mock_ctx.get.return_value = poll_resp

            client = PaperclipClient()
            result = client.request_approval("phase_end_0", {"phase": 0}, timeout_s=60)

        assert result is True
        mock_ctx.post.assert_called_once()
        mock_ctx.get.assert_called_once_with(
            "http://paperclip.test/api/v1/approvals/appr-001",
            headers={
                "Authorization": "Bearer pk_test_abc123",
                "Content-Type": "application/json",
            },
        )


class TestPaperclipRequestApprovalTimeout:
    """Approval gate timeout fails closed per T011-001."""

    def test_paperclip_request_approval_timeout(self, paperclip_env: None) -> None:
        from pipeline.control.paperclip_client import PaperclipClient

        post_resp = _mock_response(200, {"approval_id": "appr-002"})

        with patch("pipeline.control.paperclip_client.httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_ctx
            mock_ctx.post.return_value = post_resp

            client = PaperclipClient()
            result = client.request_approval("spec_signoff", {"phase": 11}, timeout_s=0)

        assert result is False
        mock_ctx.post.assert_called_once()
        mock_ctx.get.assert_not_called()


# ── WUPHF tests ───────────────────────────────────────────────────────────────


class TestWUPHFUpdateWikiMocked:
    """4. update_wiki makes a PUT to /wiki/{page} with correct page and content."""

    def test_wuphf_update_wiki_mocked(self, wuphf_env: None) -> None:
        from pipeline.control.wuphf_client import WUPHFClient

        mock_resp = _mock_response(200, {})

        with patch("pipeline.control.wuphf_client.httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_ctx
            mock_ctx.put.return_value = mock_resp

            client = WUPHFClient()
            client.update_wiki("series-bible", "# Series Bible\n\nContent here.", author="pipeline")

            mock_ctx.put.assert_called_once_with(
                "http://wuphf.test/api/v1/wiki/series-bible",
                json={"content": "# Series Bible\n\nContent here.", "author": "pipeline"},
                headers={
                    "Authorization": "Bearer wk_test_abc123",
                    "Content-Type": "application/json",
                },
            )


class TestWUPHFPostChannelMocked:
    """5. post_to_channel makes a POST to /channels/{channel}/messages."""

    def test_wuphf_post_channel_mocked(self, wuphf_env: None) -> None:
        from pipeline.control.wuphf_client import WUPHFClient

        mock_resp = _mock_response(200, {})

        with patch("pipeline.control.wuphf_client.httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_ctx
            mock_ctx.post.return_value = mock_resp

            client = WUPHFClient()
            client.post_to_channel("pipeline", "Scene ch01_sc01 complete", room="main")

            mock_ctx.post.assert_called_once_with(
                "http://wuphf.test/api/v1/channels/pipeline/messages",
                json={"message": "Scene ch01_sc01 complete", "room": "main"},
                headers={
                    "Authorization": "Bearer wk_test_abc123",
                    "Content-Type": "application/json",
                },
            )


class TestWUPHFLocalGitWiki:
    """Local WUPHF wiki mirror writes markdown files into a git-backed wiki tree."""

    def test_wuphf_update_wiki_local_git_root(self, tmp_path: Path) -> None:
        from pipeline.control.wuphf_client import WUPHFClient

        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir()
        subprocess.run(
            ["git", "init"],
            cwd=wiki_root,
            check=True,
            capture_output=True,
            text=True,
        )

        client = WUPHFClient(wiki_root=wiki_root)
        client.update_wiki(
            "series-bible/characters/char_alice",
            "# char_alice\n\nEntity type: `character`\n",
            author="pipeline",
        )

        page_path = wiki_root / "series-bible" / "characters" / "char_alice.md"
        assert page_path.exists()
        assert client.read_wiki("series-bible/characters/char_alice") == page_path.read_text(
            encoding="utf-8"
        )

        status = subprocess.run(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=wiki_root,
            check=True,
            capture_output=True,
            text=True,
        )
        assert "series-bible/characters/char_alice.md" in status.stdout


# ── ROMA tests ────────────────────────────────────────────────────────────────


class TestROMADecomposeFallback:
    """6. ROMA env var not set → falls back to local BookStructurePlanner."""

    def test_roma_decompose_fallback(self) -> None:
        from pipeline.control.roma_client import DecomposedPlan, ROMAClient

        client = ROMAClient()
        series_spec: dict[str, Any] = {
            "series_id": "test-series-fallback",
            "genre_config": {
                "chapter_count": 4,
                "word_count_target": 8000,
                "heat_curve": "rising",
            },
            "books": [
                {
                    "book_id": "test-book-001",
                    "chapter_count": 4,
                    "scenes_per_chapter": 2,
                }
            ],
        }

        plan = client.decompose(series_spec)

        assert isinstance(plan, DecomposedPlan)
        assert plan.series_id == "test-series-fallback"
        assert len(plan.book_plans) == 1
        book = plan.book_plans[0]
        assert book.book_id == "test-book-001"
        assert book.total_scenes == 8  # 4 chapters × 2 scenes
        assert len(book.act_plans) >= 1
        # Ensure every ScenePlan is populated
        all_scenes = [
            sp for ap in book.act_plans for cp in ap.chapter_plans for sp in cp.scene_plans
        ]
        assert len(all_scenes) == 8
        assert all(sp.scene_id for sp in all_scenes)


# ── Full collaboration flow ────────────────────────────────────────────────────


class TestFullCollaborationFlow:
    """7. decompose → record_cost → update_wiki: all three clients called in sequence.

    All three clients use ``import httpx`` at module level, which resolves to the
    same ``httpx`` module object.  Patching ``pipeline.control.X.httpx.Client``
    therefore patches the same underlying attribute each time — the last patch
    applied wins.  To avoid this collision we mock each client's ``_send``
    internal surface by patching ``httpx.Client`` once and routing responses by
    URL prefix.
    """

    def test_full_collaboration_flow(
        self,
        paperclip_env: None,
        wuphf_env: None,
        roma_env: None,
    ) -> None:
        from pipeline.control.paperclip_client import PaperclipClient
        from pipeline.control.roma_client import DecomposedPlan, ROMAClient
        from pipeline.control.wuphf_client import WUPHFClient

        call_order: list[str] = []

        # ── Build per-URL response registry ──────────────────────────────────
        roma_decompose_body: dict[str, Any] = {
            "series_id": "series-flow-001",
            "book_plans": [
                {
                    "book_id": "book-001",
                    "total_scenes": 4,
                    "word_count_target": 6000,
                    "act_plans": [
                        {
                            "act_number": 1,
                            "chapter_plans": [
                                {
                                    "chapter_id": "ch01",
                                    "act": 1,
                                    "scene_plans": [
                                        {
                                            "scene_id": "ch01_sc01",
                                            "act": 1,
                                            "chapter": 1,
                                            "scene_function": "meet_cute",
                                            "word_count_target": 1500,
                                            "position": 0.0,
                                        },
                                        {
                                            "scene_id": "ch01_sc02",
                                            "act": 1,
                                            "chapter": 1,
                                            "scene_function": "escalation",
                                            "word_count_target": 1500,
                                            "position": 0.33,
                                        },
                                    ],
                                }
                            ],
                        },
                        {
                            "act_number": 2,
                            "chapter_plans": [
                                {
                                    "chapter_id": "ch02",
                                    "act": 2,
                                    "scene_plans": [
                                        {
                                            "scene_id": "ch02_sc01",
                                            "act": 2,
                                            "chapter": 2,
                                            "scene_function": "black_moment",
                                            "word_count_target": 1500,
                                            "position": 0.66,
                                        },
                                        {
                                            "scene_id": "ch02_sc02",
                                            "act": 2,
                                            "chapter": 2,
                                            "scene_function": "resolution",
                                            "word_count_target": 1500,
                                            "position": 1.0,
                                        },
                                    ],
                                }
                            ],
                        },
                    ],
                }
            ],
        }

        # Shared client-level call log so we can verify HTTP verbs and URLs.
        http_calls: list[dict[str, Any]] = []

        def _make_ctx_mock() -> MagicMock:
            """Return a fresh context-manager mock whose HTTP verb methods
            route by URL prefix and record calls to ``http_calls``."""
            ctx = MagicMock()

            def _dispatch(verb: str, url: str, **kw: Any) -> MagicMock:
                http_calls.append({"verb": verb, "url": url, **kw})
                # Route by URL
                if "roma" in url and verb == "post":
                    call_order.append("roma_decompose")
                    return _mock_response(200, roma_decompose_body)
                if "paperclip" in url and "/costs" in url and verb == "post":
                    call_order.append("paperclip_record_cost")
                    return _mock_response(200, {})
                if "wuphf" in url and "/wiki/" in url and verb == "put":
                    call_order.append("wuphf_update_wiki")
                    return _mock_response(200, {})
                # Default 200 OK
                return _mock_response(200, {})

            ctx.post.side_effect = lambda url, **kw: _dispatch("post", url, **kw)
            ctx.put.side_effect = lambda url, **kw: _dispatch("put", url, **kw)
            ctx.get.side_effect = lambda url, **kw: _dispatch("get", url, **kw)
            return ctx

        shared_ctx = _make_ctx_mock()

        # A single patch covers all three clients because they share the same
        # httpx module object.
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = shared_ctx

            # ── Execute the flow ──────────────────────────────────────────────
            roma = ROMAClient()
            paperclip = PaperclipClient()
            wuphf = WUPHFClient()

            series_spec: dict[str, Any] = {"series_id": "series-flow-001"}
            plan = roma.decompose(series_spec)
            paperclip.record_cost("orchestrator", 0.003, tokens_used=200)
            wuphf.update_wiki("scene-tracker", f"Decomposed {len(plan.book_plans)} books.")

        # Verify result type and content
        assert isinstance(plan, DecomposedPlan)
        assert plan.series_id == "series-flow-001"
        assert len(plan.book_plans) == 1

        # Verify correct call order
        assert call_order == [
            "roma_decompose",
            "paperclip_record_cost",
            "wuphf_update_wiki",
        ]

        # Spot-check URLs in recorded HTTP calls
        urls = [c["url"] for c in http_calls]
        assert any("roma" in u and "decompose" in u for u in urls), (
            f"Expected ROMA /decompose URL in {urls}"
        )
        assert any("paperclip" in u and "costs" in u for u in urls), (
            f"Expected Paperclip /costs URL in {urls}"
        )
        assert any("wuphf" in u and "wiki" in u for u in urls), (
            f"Expected WUPHF /wiki URL in {urls}"
        )
