"""Unit tests for VoiceConsistencyMetric and AITellMetric."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from deepeval.test_case import LLMTestCase

from tests.eval.ai_tell_metric import AITellMetric
from tests.eval.voice_consistency_metric import VoiceConsistencyMetric

# ── Helpers ───────────────────────────────────────────────────────────────────

_CLEAN_PROSE = (
    "The rain came down hard. Sarah pressed her back against the brick wall, "
    "listening for footsteps. Nothing. She moved fast, head low, cutting across "
    "the alley before the light changed. Three blocks to the station. She could "
    "do three blocks."
)

_AI_PROSE = (
    "She thought about her feelings—complicated, layered—and felt something stir "
    "inside... It was not fear. It was something else... Something about the way "
    "he looked at her—the intensity, the unspoken words—made her chest tighten. "
    "She—he—they were caught between want and need... an impossible choice. "
    "It was not just attraction. It was a testament to everything they had been "
    "through—every scar, every silence, every stolen glance. Not because she "
    "wanted it. Because she needed it."
)


def _make_test_case(prose: str) -> LLMTestCase:
    return LLMTestCase(input="write a scene", actual_output=prose)


# ── AITellMetric tests ────────────────────────────────────────────────────────


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

    def test_ai_tell_metric_threshold(self) -> None:
        metric = AITellMetric(threshold=0.5)
        # Force score below threshold by injecting directly
        metric.score = 0.3
        assert not metric.is_successful()

    def test_ai_tell_name(self) -> None:
        assert AITellMetric().name == "AITellMetric"


# ── VoiceConsistencyMetric tests ──────────────────────────────────────────────


class TestVoiceConsistencyMetric:
    def test_voice_consistency_metric_mock(self) -> None:
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
            metric = VoiceConsistencyMetric(threshold=0.75, model_tier="test")
            tc = _make_test_case(_CLEAN_PROSE)
            score = metric.measure(tc)

        assert score == pytest.approx(0.85)
        assert metric.is_successful()
        assert metric.reason == "good"

    def test_voice_consistency_metric_failure_fallback(self) -> None:
        """Mock anthropic to raise an Exception → fallback score 0.5, no crash."""
        mock_client_instance = MagicMock()
        mock_client_instance.messages.create.side_effect = RuntimeError("API down")

        with patch("anthropic.Anthropic", return_value=mock_client_instance):
            metric = VoiceConsistencyMetric(threshold=0.75, model_tier="test")
            tc = _make_test_case(_CLEAN_PROSE)
            score = metric.measure(tc)

        assert score == pytest.approx(0.5)
        assert metric.reason == "evaluation failed"

    def test_voice_consistency_name(self) -> None:
        assert VoiceConsistencyMetric().name == "VoiceConsistencyMetric"
