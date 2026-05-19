"""AITellMetric — DeepEval metric for AI-tell density detection."""

from __future__ import annotations

import logging

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from pipeline.agents.structural_analysis import StructuralAnalyzer

logger = logging.getLogger(__name__)

_SEVERITY_WEIGHTS: dict[str, int] = {
    "critical": 3,
    "high": 2,
    "medium": 1,
    "info": 0,
}


class AITellMetric(BaseMetric):  # type: ignore[no-untyped-call]
    """DeepEval metric that scores prose by deterministic AI-tell density.

    Score of 1.0 = perfectly clean; 0.0 = extremely dense with AI tells.
    """

    def __init__(self, threshold: float = 0.5, use_llm_judge: bool = False) -> None:
        self.threshold = threshold
        self.use_llm_judge = use_llm_judge
        self.score: float = 0.0
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase) -> float:
        """Analyze prose for AI-tell density and return a score in [0.0, 1.0]."""
        prose = test_case.actual_output or ""
        report = StructuralAnalyzer().analyze(prose)
        word_count = len(prose.split())

        weighted = sum(_SEVERITY_WEIGHTS.get(i.severity, 1) for i in report.issues)
        density = weighted / max(1, word_count / 1000)

        # Normalize: 0 issues → 1.0 (clean); density ≥ 10 → 0.0 (terrible)
        score = max(0.0, 1.0 - density / 10.0)

        # LLM judge stub: only invoked for critical issues when use_llm_judge is True.
        # In V1 the LLM re-score is not implemented — density score is kept as-is.
        if self.use_llm_judge and any(i.severity == "critical" for i in report.issues):
            logger.debug(
                "AITellMetric: %d critical issue(s) detected; LLM re-score deferred to V2.",
                sum(1 for i in report.issues if i.severity == "critical"),
            )

        self.score = round(score, 4)
        self.reason = f"{len(report.issues)} structural issues; weighted density={density:.2f}"
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        """Async wrapper — delegates to synchronous measure()."""
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.score >= self.threshold

    @property
    def name(self) -> str:
        return "AITellMetric"
