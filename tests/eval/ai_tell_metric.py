"""AITellMetric - deterministic DeepEval metric for AI-tell density detection."""

from __future__ import annotations

import logging
import re

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

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
        word_count = len(re.findall(r"\b\w+(?:'\w+)?\b", prose))
        if word_count == 0:
            self.score = 0.0
            self.reason = "empty prose"
            return self.score

        severities, source = _detect_issue_severities(prose)
        weighted = sum(_SEVERITY_WEIGHTS.get(severity, 1) for severity in severities)
        density = weighted / max(1, word_count / 1000)

        score = max(0.0, 1.0 - density / 10.0)

        if self.use_llm_judge and any(severity == "critical" for severity in severities):
            logger.debug(
                "AITellMetric: %d critical issue(s) detected; LLM re-score deferred to V2.",
                sum(1 for severity in severities if severity == "critical"),
            )

        self.score = round(score, 4)
        self.reason = (
            f"{len(severities)} structural issues via {source}; weighted density={density:.2f}"
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        """Async wrapper - delegates to synchronous measure()."""
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.score >= self.threshold

    @property
    def name(self) -> str:
        return "AITellMetric"


def _detect_issue_severities(prose: str) -> tuple[list[str], str]:
    """Use StructuralAnalyzer when available; fallback to local deterministic regexes."""
    try:
        from pipeline.agents.structural_analysis import StructuralAnalyzer  # noqa: PLC0415

        report = StructuralAnalyzer().analyze(prose)
        return [issue.severity for issue in report.issues], "StructuralAnalyzer"
    except Exception as exc:  # noqa: BLE001
        logger.warning("AITellMetric StructuralAnalyzer failed; using fallback: %s", exc)
        return _fallback_issue_severities(prose), "fallback"


def _fallback_issue_severities(prose: str) -> list[str]:
    severities: list[str] = []
    word_count = max(1, len(re.findall(r"\b\w+(?:'\w+)?\b", prose)))
    per_1k = word_count / 1000.0

    critical_patterns = (r"\ba testament to\b",)
    high_patterns = (
        r"\bIt(?:'s| is) not [^.!?]+\.\s+It(?:'s| is)\b",
        r"\bNot because [^.!?]+\.\s+Because\b",
    )
    medium_patterns = (
        r"\bsomething about\b",
        r"\bin that moment\b",
        r"\bevery fiber of (?:her|his|their) being\b",
    )

    for pattern in critical_patterns:
        severities.extend("critical" for _ in re.finditer(pattern, prose, flags=re.IGNORECASE))
    for pattern in high_patterns:
        severities.extend("high" for _ in re.finditer(pattern, prose, flags=re.IGNORECASE))
    for pattern in medium_patterns:
        severities.extend("medium" for _ in re.finditer(pattern, prose, flags=re.IGNORECASE))

    em_dash_count = prose.count("—") + prose.count("–")
    if per_1k > 0 and em_dash_count / per_1k > 8.0:
        severities.append("medium")

    ellipsis_count = prose.count("...") + prose.count("…")
    if per_1k > 0 and ellipsis_count / per_1k > 4.0:
        severities.append("medium")

    return severities
