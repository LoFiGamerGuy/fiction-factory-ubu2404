"""VoiceConsistencyMetric — DeepEval custom metric using Claude-as-judge."""

from __future__ import annotations

import json
import logging

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

logger = logging.getLogger(__name__)

_TEST_MODEL = "claude-haiku-3-5-20241022"
_PROD_MODEL = "claude-sonnet-4-6"

_PROMPT_TEMPLATE = (
    "Score this prose 0.0–1.0 for voice consistency. "
    "Consider: natural pacing, authentic character voice, avoidance of AI-tell patterns. "
    "Prose: {prose}. "
    'Return JSON: {{"score": float, "rationale": string}}'
)


class VoiceConsistencyMetric(BaseMetric):  # type: ignore[no-untyped-call]
    """DeepEval custom metric that uses Claude as an LLM judge for voice consistency."""

    def __init__(self, threshold: float = 0.75, model_tier: str = "test") -> None:
        self.threshold = threshold
        self.model_tier = model_tier
        self.score: float = 0.0
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase) -> float:
        """Score prose for voice consistency using Claude-as-judge."""
        model = _TEST_MODEL if self.model_tier == "test" else _PROD_MODEL
        prose = test_case.actual_output or ""
        prompt = _PROMPT_TEMPLATE.format(prose=prose[:2000])

        try:
            import anthropic  # noqa: PLC0415

            client = anthropic.Anthropic()
            response = client.messages.create(
                model=model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            # Content block may be TextBlock or other types; guard with hasattr.
            block = response.content[0]
            raw: str = block.text if hasattr(block, "text") else ""
            result = json.loads(raw)
            self.score = float(result["score"])
            self.reason = str(result["rationale"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("VoiceConsistencyMetric evaluation failed: %s", exc)
            self.score = 0.5
            self.reason = "evaluation failed"

        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        """Async wrapper — delegates to synchronous measure()."""
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.score >= self.threshold

    @property
    def name(self) -> str:
        return "VoiceConsistencyMetric"
