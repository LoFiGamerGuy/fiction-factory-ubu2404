"""Unit tests for VoiceConsistencyMetric, AITellMetric, and run_eval."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from deepeval.test_case import LLMTestCase

from tests.eval.ai_tell_metric import AITellMetric
from tests.eval.voice_consistency_metric import VoiceConsistencyMetric

run_eval = importlib.import_module("scripts.run_eval")

# -- Helpers -----------------------------------------------------------------

_CLEAN_PROSE = (
    "The rain came down hard. Sarah pressed her back against the brick wall, "
    "listening for footsteps. Nothing. She moved fast, head low, cutting across "
    "the alley before the light changed. Three blocks to the station. She could "
    "do three blocks."
)

_AI_PROSE = (
    "She thought about her feelings--complicated, layered--and felt something stir "
    "inside... It was not fear. It was something else... Something about the way "
    "he looked at her--the intensity, the unspoken words--made her chest tighten. "
    "She--he--they were caught between want and need... an impossible choice. "
    "It was not just attraction. It was a testament to everything they had been "
    "through--every scar, every silence, every stolen glance. Not because she "
    "wanted it. Because she needed it."
)


def _make_test_case(prose: str) -> LLMTestCase:
    return LLMTestCase(input="write a scene", actual_output=prose)


# -- AITellMetric tests ------------------------------------------------------


class TestAITellMetric:
    def test_ai_tell_metric_clean_prose(self) -> None:
        metric = AITellMetric(threshold=0.5)
        tc = _make_test_case(_CLEAN_PROSE)
        score = metric.measure(tc)
        assert score > 0.8, f"expected clean prose score > 0.8, got {score}"
        assert metric.is_successful()

    def test_ai_tell_metric_ai_prose(self) -> None:
        metric = AITellMetric(threshold=0.5)
        tc = _make_test_case(_AI_PROSE)
        clean_metric = AITellMetric(threshold=0.5)
        clean_score = clean_metric.measure(_make_test_case(_CLEAN_PROSE))
        ai_score = metric.measure(tc)
        assert ai_score < clean_score, (
            f"AI prose score ({ai_score}) should be lower than clean prose score ({clean_score})"
        )

    def test_ai_tell_metric_empty_prose_fails(self) -> None:
        metric = AITellMetric(threshold=0.5)
        score = metric.measure(_make_test_case(""))
        assert score == 0.0
        assert not metric.is_successful()
        assert metric.reason == "empty prose"

    def test_ai_tell_metric_threshold(self) -> None:
        metric = AITellMetric(threshold=0.5)
        metric.score = 0.3
        assert not metric.is_successful()

    def test_ai_tell_name(self) -> None:
        assert AITellMetric().name == "AITellMetric"


# -- VoiceConsistencyMetric tests -------------------------------------------


class TestVoiceConsistencyMetric:
    def test_voice_consistency_metric_default_offline(self) -> None:
        """Default path is deterministic and does not call Anthropic."""
        with patch("anthropic.Anthropic") as mock_anthropic:
            metric = VoiceConsistencyMetric(threshold=0.75, model_tier="test")
            score = metric.measure(_make_test_case(_CLEAN_PROSE))

        mock_anthropic.assert_not_called()
        assert score > 0.75
        assert metric.is_successful()
        assert "deterministic heuristic" in metric.reason

    def test_voice_consistency_metric_llm_mock(self) -> None:
        """Mock anthropic.Anthropic to return a known JSON response."""
        mock_content = MagicMock()
        mock_content.text = '{"score": 0.85, "rationale": "good"}'
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        mock_messages = MagicMock()
        mock_messages.create.return_value = mock_response
        mock_client_instance = MagicMock()
        mock_client_instance.messages = mock_messages

        with patch("anthropic.Anthropic", return_value=mock_client_instance):
            metric = VoiceConsistencyMetric(
                threshold=0.75,
                model_tier="test",
                use_llm_judge=True,
            )
            tc = _make_test_case(_CLEAN_PROSE)
            score = metric.measure(tc)

        assert score == pytest.approx(0.85)
        assert metric.is_successful()
        assert metric.reason == "good"

    def test_voice_consistency_metric_failure_fallback_is_deterministic(self) -> None:
        """Mock anthropic to raise an Exception; fallback score matches offline path."""
        offline = VoiceConsistencyMetric(threshold=0.75, model_tier="test", use_llm_judge=False)
        expected = offline.measure(_make_test_case(_CLEAN_PROSE))

        mock_client_instance = MagicMock()
        mock_client_instance.messages.create.side_effect = RuntimeError("API down")

        with patch("anthropic.Anthropic", return_value=mock_client_instance):
            metric = VoiceConsistencyMetric(
                threshold=0.75,
                model_tier="test",
                use_llm_judge=True,
            )
            tc = _make_test_case(_CLEAN_PROSE)
            score = metric.measure(tc)

        assert score == pytest.approx(expected)
        assert metric.reason.startswith("LLM evaluation failed;")

    def test_voice_consistency_ai_prose_scores_lower_than_clean(self) -> None:
        clean = VoiceConsistencyMetric(use_llm_judge=False).measure(_make_test_case(_CLEAN_PROSE))
        ai = VoiceConsistencyMetric(use_llm_judge=False).measure(_make_test_case(_AI_PROSE))
        assert ai < clean

    def test_voice_consistency_name(self) -> None:
        assert VoiceConsistencyMetric().name == "VoiceConsistencyMetric"


# -- scripts/run_eval.py tests ----------------------------------------------


class TestRunEval:
    def test_run_eval_passes_with_relaxed_thresholds(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        scene = tmp_path / "scene.md"
        scene.write_text(_CLEAN_PROSE, encoding="utf-8")

        exit_code = run_eval.main(
            [
                "--scene",
                str(scene),
                "--voice-threshold",
                "0.10",
                "--ai-tell-threshold",
                "0.10",
            ]
        )

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "VoiceConsistencyMetric" in captured.out
        assert "AITellMetric" in captured.out
        assert "Result: PASS" in captured.out

    def test_run_eval_fails_below_threshold(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        scene = tmp_path / "scene.md"
        scene.write_text(_AI_PROSE, encoding="utf-8")

        exit_code = run_eval.main(
            [
                "--scene",
                str(scene),
                "--voice-threshold",
                "0.99",
                "--ai-tell-threshold",
                "0.99",
            ]
        )

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Result: FAIL" in captured.out

    def test_run_eval_finds_latest_completed_scene(self, tmp_path: Path) -> None:
        old_scene_dir = tmp_path / "run_a" / "scenes"
        new_scene_dir = tmp_path / "run_b" / "scenes"
        old_scene_dir.mkdir(parents=True)
        new_scene_dir.mkdir(parents=True)
        old_scene = old_scene_dir / "old.md"
        new_scene = new_scene_dir / "new.md"
        old_scene.write_text("old", encoding="utf-8")
        new_scene.write_text("new", encoding="utf-8")
        os.utime(old_scene, (1, 1))
        os.utime(new_scene, (2, 2))

        assert run_eval._find_latest_completed_scene(tmp_path) == new_scene
