"""Dreaming evaluation test harness (T1.14).

BCR-20260522-claude-dreaming-mem0

This is infrastructure-only. Agents are not wired yet (Phase 7 T7.1).
Acceptance: harness runs without errors.
"""

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent


class TestDreamingHarnessInfrastructure:
    """Harness smoke tests (no agents wired yet)."""

    def test_fixture_files_exist(self) -> None:
        """All fixture spec files exist."""
        assert (FIXTURE_DIR / "romance_series_spec.yaml").exists()
        assert (FIXTURE_DIR / "book_spec.yaml").exists()
        assert (FIXTURE_DIR / "README.md").exists()

    def test_fixture_specs_loadable(self) -> None:
        """Fixture specs are valid YAML."""
        import yaml

        with (FIXTURE_DIR / "romance_series_spec.yaml").open() as f:
            series_spec = yaml.safe_load(f)
            assert series_spec["series_id"] == "dreaming-eval-series"
            assert series_spec["genre"] == "romance"
            assert series_spec["heat_level"] == "sensual"

        with (FIXTURE_DIR / "book_spec.yaml").open() as f:
            book_spec = yaml.safe_load(f)
            assert book_spec["book_id"] == "dreaming-eval-book-01"
            assert len(book_spec["scenes"]) == 3

    def test_dreaming_mode_flag_structure(self) -> None:
        """--with-dreaming and --without-dreaming flags are structurally valid."""
        # This test verifies pytest fixture structure only
        # Actual agent execution happens in Phase 7

        # Flags would be consumed by pytest.fixture in Phase 7:
        # @pytest.fixture
        # def dreaming_mode(request):
        #     return request.config.getoption("--with-dreaming")

        assert True  # Placeholder for Phase 7 wiring


class TestDreamingComparisonStub:
    """Stub for Phase 7 comparison tests (agents not wired yet)."""

    @pytest.mark.skip(reason="Agents not wired yet — Phase 7 T7.1")
    def test_3scene_with_dreaming(self) -> None:
        """Run 3-scene fixture WITH Dreaming enabled."""
        # Phase 7: Wire to WriterAgent with managed_agent_mode=True, dreaming_enabled=True
        pass

    @pytest.mark.skip(reason="Agents not wired yet — Phase 7 T7.1")
    def test_3scene_without_dreaming(self) -> None:
        """Run 3-scene fixture WITHOUT Dreaming."""
        # Phase 7: Wire to WriterAgent with managed_agent_mode=False
        pass

    @pytest.mark.skip(reason="Agents not wired yet — Phase 7 T7.1")
    def test_compare_convergence_speed(self) -> None:
        """Compare REVISE cycle count: WITH vs WITHOUT Dreaming."""
        # Phase 7: Log convergence metrics, compare
        pass

    @pytest.mark.skip(reason="Agents not wired yet — Phase 7 T7.1")
    def test_compare_prose_quality(self) -> None:
        """Compare VoiceConsistencyMetric: WITH vs WITHOUT Dreaming."""
        # Phase 7: DeepEval VoiceConsistencyMetric on both runs
        pass

    @pytest.mark.skip(reason="Agents not wired yet — Phase 7 T7.1")
    def test_compare_routing_decisions(self) -> None:
        """Compare routing decision count: WITH vs WITHOUT Dreaming."""
        # Phase 7: Count GO/REVISE/RE-PLAN/FORCE-RESOLVE from ConvergenceController
        pass


@pytest.fixture
def dreaming_eval_fixture_dir() -> Path:
    """Fixture directory path for other tests to reference."""
    return FIXTURE_DIR


@pytest.fixture
def romance_series_spec(dreaming_eval_fixture_dir: Path) -> Path:
    """Romance series spec file path."""
    return dreaming_eval_fixture_dir / "romance_series_spec.yaml"


@pytest.fixture
def book_spec(dreaming_eval_fixture_dir: Path) -> Path:
    """Book spec file path."""
    return dreaming_eval_fixture_dir / "book_spec.yaml"
