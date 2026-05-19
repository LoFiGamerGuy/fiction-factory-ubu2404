"""Unit tests — Phase 6 agent foundation: all 8 core modules."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from pipeline.core.agent_context import AgentContext
from pipeline.core.base_agent import BaseAgent
from pipeline.core.context_manager import (
    ContextBundle,
    ContextManager,
)
from pipeline.core.context_pack_builder import ContextPackBuilder, _compute_provenance_hash
from pipeline.core.job_context import JobContext
from pipeline.core.model_router import ModelRouter
from pipeline.core.project_layout import ProjectLayout
from pipeline.core.voice_profile import VoiceProfile

WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
FIXTURE_AUTHOR_PROFILE = WORKSPACE_ROOT / "profiles" / "author" / "fixture.yaml"
AUTHOR_SCHEMA = WORKSPACE_ROOT / "schemas" / "profiles" / "author_profile.schema.json"
MODEL_ROUTER_JSON = WORKSPACE_ROOT / "model_router.json"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_spec() -> Any:
    from pipeline.profiles.profile_registry import ProfileRegistry

    registry = ProfileRegistry(workspace_root=WORKSPACE_ROOT)
    return registry.compose(
        book_id="test-book",
        series_id="test-series",
        author_name="fixture",
        genre_name="fixture",
        audience_name="fixture",
        sensitivity_name="fixture",
        goal_name="fixture",
    )


def _make_layout(tmp_path: Path) -> ProjectLayout:
    return ProjectLayout(series_root=tmp_path / "series" / "test-series", book_id="test-book")


def _make_ledger_manager(tmp_path: Path) -> Any:
    from pipeline.ledgers.ledger_manager import LedgerManager

    return LedgerManager(book_id="test-book", data_root=tmp_path / "data")


def _make_agent_context(tmp_path: Path) -> AgentContext:
    layout = _make_layout(tmp_path)
    loader = MagicMock()
    ledger_mgr = _make_ledger_manager(tmp_path)
    return AgentContext(
        project_layout=layout,
        spec_loader=loader,
        ledger_manager=ledger_mgr,
        log_path=tmp_path / "logs" / "agents.jsonl",
        output_dir=tmp_path / "output",
        model_tier="test",
    )


# ── ProjectLayout ──────────────────────────────────────────────────────────────


class TestProjectLayout:
    def test_path_methods_return_paths(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        assert isinstance(layout.series_spec_path(), Path)
        assert isinstance(layout.book_spec_path(), Path)
        assert isinstance(layout.cost_log_path(), Path)

    def test_scene_output_path_includes_chapter_and_scene(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        p = layout.scene_output_path(3, "ch03_sc07")
        assert "ch03" in p.name
        assert "sc07" in p.name

    def test_ledger_db_path_includes_name(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        p = layout.ledger_db_path("book_metrics")
        assert "book_metrics" in p.name

    def test_context_pack_path_includes_agent_and_scene(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        p = layout.context_pack_path("writer_agent", "ch01_sc01")
        assert "writer_agent" in str(p)
        assert "ch01_sc01" in p.name

    def test_series_root_embedded_in_all_paths(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        assert str(layout.series_root) in str(layout.book_spec_path())
        assert str(layout.series_root) in str(layout.cost_log_path())


# ── AgentContext ───────────────────────────────────────────────────────────────


class TestAgentContext:
    def test_valid_construction_succeeds(self, tmp_path: Path) -> None:
        ctx = _make_agent_context(tmp_path)
        assert ctx.model_tier == "test"
        assert ctx.voice_exemplar_manager is None

    def test_missing_project_layout_raises(self, tmp_path: Path) -> None:
        ledger_mgr = _make_ledger_manager(tmp_path)
        with pytest.raises(ValueError, match="project_layout"):
            AgentContext(
                project_layout=None,
                spec_loader=MagicMock(),
                ledger_manager=ledger_mgr,
                log_path=tmp_path / "log.jsonl",
                output_dir=tmp_path / "out",
            )

    def test_missing_ledger_manager_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="ledger_manager"):
            AgentContext(
                project_layout=_make_layout(tmp_path),
                spec_loader=MagicMock(),
                ledger_manager=None,  # type: ignore[arg-type]
                log_path=tmp_path / "log.jsonl",
                output_dir=tmp_path / "out",
            )

    def test_missing_log_path_raises(self, tmp_path: Path) -> None:
        ledger_mgr = _make_ledger_manager(tmp_path)
        with pytest.raises(ValueError, match="log_path"):
            AgentContext(
                project_layout=_make_layout(tmp_path),
                spec_loader=MagicMock(),
                ledger_manager=ledger_mgr,
                log_path=None,  # type: ignore[arg-type]
                output_dir=tmp_path / "out",
            )

    def test_output_dir_created_on_init(self, tmp_path: Path) -> None:
        out = tmp_path / "new_output_dir"
        assert not out.exists()
        _make_agent_context.__wrapped__ = None  # type: ignore[attr-defined]
        ledger_mgr = _make_ledger_manager(tmp_path)
        AgentContext(
            project_layout=_make_layout(tmp_path),
            spec_loader=MagicMock(),
            ledger_manager=ledger_mgr,
            log_path=tmp_path / "log.jsonl",
            output_dir=out,
        )
        assert out.exists()


# ── ModelRouter ────────────────────────────────────────────────────────────────


class TestModelRouterTierRouting:
    def test_test_tier_anthropic(self) -> None:
        router = ModelRouter(config_path=MODEL_ROUTER_JSON)
        assert router.route("anthropic", "test") == "claude-haiku-4-5-20251001"

    def test_test_tier_openai(self) -> None:
        router = ModelRouter(config_path=MODEL_ROUTER_JSON)
        assert router.route("openai", "test") == "gpt-4.1-mini"

    def test_production_tier_anthropic(self) -> None:
        router = ModelRouter(config_path=MODEL_ROUTER_JSON)
        assert router.route("anthropic", "production") == "claude-sonnet-4-6"

    def test_production_tier_openai(self) -> None:
        router = ModelRouter(config_path=MODEL_ROUTER_JSON)
        assert router.route("openai", "production") == "gpt-4.1"

    def test_unknown_provider_raises(self) -> None:
        router = ModelRouter(config_path=MODEL_ROUTER_JSON)
        with pytest.raises(ValueError, match="provider"):
            router.route("unknown_provider", "test")

    def test_unknown_tier_raises(self) -> None:
        router = ModelRouter(config_path=MODEL_ROUTER_JSON)
        with pytest.raises(ValueError, match="tier"):
            router.route("anthropic", "nonexistent_tier")


class TestModelRouterInstructorWrapping:
    """Verify call() returns a pydantic model, not raw text."""

    class _SimpleModel(BaseModel):
        answer: str

    def test_call_returns_pydantic_model_anthropic(self, tmp_path: Path) -> None:
        router = ModelRouter(config_path=MODEL_ROUTER_JSON)
        expected = self._SimpleModel(answer="hello")

        mock_client = MagicMock()
        mock_client.messages.create.return_value = expected

        with (
            patch("pipeline.core.model_router.os.environ.get", return_value="fake-key"),
            patch(
                "pipeline.core.model_router.ModelRouter._call_anthropic",
                return_value=expected,
            ),
        ):
            result = router.call(
                messages=[{"role": "user", "content": "test"}],
                response_model=self._SimpleModel,
                provider="anthropic",
            )

        assert isinstance(result, self._SimpleModel)
        assert result.answer == "hello"

    def test_call_returns_pydantic_model_openai(self, tmp_path: Path) -> None:
        router = ModelRouter(config_path=MODEL_ROUTER_JSON)
        expected = self._SimpleModel(answer="world")

        with patch(
            "pipeline.core.model_router.ModelRouter._call_openai",
            return_value=expected,
        ):
            result = router.call(
                messages=[{"role": "user", "content": "test"}],
                response_model=self._SimpleModel,
                provider="openai",
            )

        assert isinstance(result, self._SimpleModel)
        assert result.answer == "world"

    def test_cost_log_written(self, tmp_path: Path) -> None:
        cost_log = tmp_path / "data" / "cost_log.jsonl"
        router = ModelRouter(config_path=MODEL_ROUTER_JSON, cost_log_path=cost_log)
        expected = self._SimpleModel(answer="logged")

        with patch(
            "pipeline.core.model_router.ModelRouter._call_openai",
            return_value=expected,
        ):
            router.call(
                messages=[{"role": "user", "content": "test"}],
                response_model=self._SimpleModel,
                provider="openai",
                job_id="j1",
                agent_id="writer",
            )

        assert cost_log.exists()
        entry = json.loads(cost_log.read_text().strip())
        assert entry["job_id"] == "j1"
        assert entry["agent_id"] == "writer"
        assert entry["provider"] == "openai"
        assert "model" in entry
        assert "timestamp" in entry


# ── VoiceProfile ───────────────────────────────────────────────────────────────


class TestVoiceProfile:
    def test_load_fixture_profile(self) -> None:
        vp = VoiceProfile.load(FIXTURE_AUTHOR_PROFILE, schema_path=AUTHOR_SCHEMA)
        assert vp.profile_id == "fixture-author-001"
        assert vp.version == "1.0.0"
        assert vp.display_name == "Fixture Author"

    def test_voice_axes_populated(self) -> None:
        vp = VoiceProfile.load(FIXTURE_AUTHOR_PROFILE, schema_path=AUTHOR_SCHEMA)
        assert "sentence_level" in vp.voice_axes
        assert "lexical" in vp.voice_axes

    def test_enforcement_weights_typed(self) -> None:
        vp = VoiceProfile.load(FIXTURE_AUTHOR_PROFILE, schema_path=AUTHOR_SCHEMA)
        assert isinstance(vp.enforcement_weights, dict)
        for v in vp.enforcement_weights.values():
            assert isinstance(v, float)

    def test_forbidden_constructions_compiled(self) -> None:
        vp = VoiceProfile.load(FIXTURE_AUTHOR_PROFILE, schema_path=AUTHOR_SCHEMA)
        for pat in vp.forbidden_constructions_compiled:
            assert isinstance(pat, re.Pattern)

    def test_forbidden_constructions_match(self) -> None:
        vp = VoiceProfile.load(FIXTURE_AUTHOR_PROFILE, schema_path=AUTHOR_SCHEMA)
        raw = vp.forbidden_constructions_raw
        compiled = vp.forbidden_constructions_compiled
        assert len(raw) == len(compiled)
        if raw:
            assert compiled[0].search(raw[0].strip("\\b")) is not None

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            VoiceProfile.load(tmp_path / "nonexistent.yaml")

    def test_schema_validation_rejects_bad_yaml(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("profile_id: x\nversion: '1'\n")  # missing required fields
        with pytest.raises(ValueError, match="schema validation"):
            VoiceProfile.load(bad, schema_path=AUTHOR_SCHEMA)


# ── ContextManager ─────────────────────────────────────────────────────────────


class TestContextManager:
    def _make_dashboard_mock(self) -> MagicMock:
        from pipeline.ledgers.ledger_manager import AuthorDashboard

        dash = AuthorDashboard(
            book_id="test-book",
            scene_id="ch01_sc01",
            word_count_total=1000,
            interiority_pct_running=0.30,
            dialogue_ratio_running=0.40,
            ai_tell_count_total=2,
            character_arcs={},
            intimacy_pairs={},
        )
        mgr = MagicMock()
        mgr.get_dashboard_summary.return_value = dash
        return mgr

    def test_assemble_returns_context_bundle(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        spec = _make_spec()
        ledger_mock = self._make_dashboard_mock()
        cm = ContextManager(project_layout=layout, ledger_manager=ledger_mock)
        jc = JobContext(
            job_id="j1",
            series_id="s",
            book_id="test-book",
            chapter_id=1,
            scene_id="ch01_sc01",
            spec=spec,
        )
        bundle = cm.assemble(jc, scene_brief="Two characters meet.")
        assert isinstance(bundle, ContextBundle)

    def test_scene_brief_in_scene_tier(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        spec = _make_spec()
        ledger_mock = self._make_dashboard_mock()
        cm = ContextManager(project_layout=layout, ledger_manager=ledger_mock)
        jc = JobContext(
            job_id="j1",
            series_id="s",
            book_id="test-book",
            chapter_id=1,
            scene_id="ch01_sc01",
            spec=spec,
        )
        bundle = cm.assemble(jc, scene_brief="Unique scene brief content.")
        assert "Unique scene brief content." in bundle.scene_tier

    def test_author_dashboard_injected(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        spec = _make_spec()
        ledger_mock = self._make_dashboard_mock()
        cm = ContextManager(project_layout=layout, ledger_manager=ledger_mock)
        jc = JobContext(
            job_id="j1",
            series_id="s",
            book_id="test-book",
            chapter_id=1,
            scene_id="ch01_sc01",
            spec=spec,
        )
        bundle = cm.assemble(jc, scene_brief="Test")
        assert bundle.author_dashboard_summary != {}
        assert "book_id" in bundle.author_dashboard_summary

    def test_scene_tier_truncated_when_oversized(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        spec = _make_spec()
        ledger_mock = self._make_dashboard_mock()
        cm = ContextManager(
            project_layout=layout,
            ledger_manager=ledger_mock,
            scene_tier_max_chars=100,
        )
        jc = JobContext(
            job_id="j1",
            series_id="s",
            book_id="test-book",
            chapter_id=1,
            scene_id="ch01_sc01",
            spec=spec,
        )
        big_brief = "x" * 5000
        bundle = cm.assemble(jc, scene_brief=big_brief)
        assert len(bundle.scene_tier) <= 100

    def test_book_tier_truncated_when_oversized(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        spec = _make_spec()
        ledger_mock = self._make_dashboard_mock()
        # Write a very large bible
        bible_path = layout.series_bible_path()
        bible_path.parent.mkdir(parents=True, exist_ok=True)
        bible_path.write_text("b" * 10_000)
        cm = ContextManager(
            project_layout=layout,
            ledger_manager=ledger_mock,
            book_tier_max_chars=200,
        )
        jc = JobContext(
            job_id="j1",
            series_id="s",
            book_id="test-book",
            chapter_id=1,
            scene_id="ch01_sc01",
            spec=spec,
        )
        bundle = cm.assemble(jc)
        assert len(bundle.book_tier) <= 200


# ── ContextPackBuilder ─────────────────────────────────────────────────────────


class TestContextPackBuilder:
    def _make_bundle(self) -> ContextBundle:
        return ContextBundle(
            scene_tier="scene content here",
            book_tier="book content here",
            series_tier="series content here",
            author_dashboard_summary={"book_id": "test-book"},
        )

    def test_build_returns_context_pack(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        builder = ContextPackBuilder(project_layout=layout)
        pack = builder.build(
            job_id="j1",
            agent_id="writer_agent",
            scene_id="ch01_sc01",
            context_bundle=self._make_bundle(),
        )
        assert pack.agent_id == "writer_agent"
        assert pack.scene_id == "ch01_sc01"
        assert pack.job_id == "j1"

    def test_provenance_json_written(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        builder = ContextPackBuilder(project_layout=layout)
        builder.build(
            job_id="j1",
            agent_id="writer_agent",
            scene_id="ch01_sc01",
            context_bundle=self._make_bundle(),
        )
        prov_path = layout.provenance_path("writer_agent", "ch01_sc01")
        assert prov_path.exists()
        prov = json.loads(prov_path.read_text())
        assert "source_file_hashes" in prov
        assert "view_schema_version" in prov
        assert "generated_at" in prov
        assert "agent_id" in prov
        assert "provenance_hash" in prov

    def test_provenance_hash_matches_content(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        builder = ContextPackBuilder(project_layout=layout)
        bundle = self._make_bundle()
        pack = builder.build(
            job_id="j1",
            agent_id="writer_agent",
            scene_id="ch01_sc01",
            context_bundle=bundle,
        )
        expected_hash = _compute_provenance_hash(
            context_tiers=bundle.as_tiers_dict(),
            source_file_hashes={},
            view_schema_version=pack.view_schema_version,
            agent_id="writer_agent",
            scene_id="ch01_sc01",
        )
        assert pack.provenance_hash == expected_hash

    def test_pack_json_written_to_disk(self, tmp_path: Path) -> None:
        layout = _make_layout(tmp_path)
        builder = ContextPackBuilder(project_layout=layout)
        pack = builder.build(
            job_id="j1",
            agent_id="writer_agent",
            scene_id="ch01_sc01",
            context_bundle=self._make_bundle(),
        )
        assert pack.output_path.exists()
        data = json.loads(pack.output_path.read_text())
        assert data["agent_id"] == "writer_agent"
        assert "context_tiers" in data


# ── BaseAgent ──────────────────────────────────────────────────────────────────


class TestBaseAgent:
    def test_missing_impl_class_raises(self, tmp_path: Path) -> None:
        ctx = _make_agent_context(tmp_path)

        class NoImplAgent(BaseAgent):
            version: str = "1.0"  # type: ignore[misc]

            def _execute(self, job_context: JobContext) -> JobContext:
                return job_context

        with pytest.raises(TypeError, match="impl_class"):
            NoImplAgent(ctx)

    def test_invalid_impl_class_raises(self, tmp_path: Path) -> None:
        ctx = _make_agent_context(tmp_path)

        class BadImplAgent(BaseAgent):
            impl_class = "invalid_value"
            version = "1.0"

            def _execute(self, job_context: JobContext) -> JobContext:
                return job_context

        with pytest.raises(TypeError, match="invalid"):
            BadImplAgent(ctx)

    def test_valid_impl_class_constructs(self, tmp_path: Path) -> None:
        ctx = _make_agent_context(tmp_path)

        class GoodAgent(BaseAgent):
            impl_class = "deterministic"
            version = "1.0"

            def _execute(self, job_context: JobContext) -> JobContext:
                return job_context

        agent = GoodAgent(ctx)
        assert agent.ctx is ctx

    def test_run_emits_structured_log(self, tmp_path: Path) -> None:
        ctx = _make_agent_context(tmp_path)
        spec = _make_spec()

        class LoggingAgent(BaseAgent):
            impl_class = "deterministic"
            version = "0.1"

            def _execute(self, job_context: JobContext) -> JobContext:
                return job_context

        agent = LoggingAgent(ctx)
        jc = JobContext(
            job_id="j1",
            series_id="s",
            book_id="b",
            chapter_id=1,
            scene_id="ch01_sc01",
            spec=spec,
        )
        agent.run(jc)

        assert ctx.log_path.exists()
        entry = json.loads(ctx.log_path.read_text().strip())
        assert entry["component_id"] == "LoggingAgent"
        assert entry["impl_class"] == "deterministic"
        assert entry["job_id"] == "j1"
        assert "input_hash" in entry
        assert "output_hash" in entry
        assert "duration_ms" in entry
        assert "timestamp" in entry

    def test_all_three_impl_classes_accepted(self, tmp_path: Path) -> None:
        ctx = _make_agent_context(tmp_path)
        for impl in ("deterministic", "llm", "hybrid"):

            class Agent(BaseAgent):
                version = "1.0"

                def _execute(self, job_context: JobContext) -> JobContext:
                    return job_context

            Agent.impl_class = impl
            assert Agent(ctx).ctx is ctx
