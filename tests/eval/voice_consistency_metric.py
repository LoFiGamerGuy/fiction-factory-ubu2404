"""VoiceConsistencyMetric - DeepEval metric with deterministic offline fallback."""

from __future__ import annotations

import json
import logging
import os
import re
import statistics

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

logger = logging.getLogger(__name__)

_TEST_MODEL = "claude-haiku-3-5-20241022"
_PROD_MODEL = "claude-sonnet-4-6"

_PROMPT_TEMPLATE = (
    "Score this prose 0.0-1.0 for voice consistency. "
    "Consider: natural pacing, authentic character voice, avoidance of AI-tell patterns. "
    "Prose: {prose}. "
    'Return JSON: {{"score": float, "rationale": string}}'
)

_VOICE_TELL_PATTERNS = (
    r"\ba testament to\b",
    r"\bevery fiber of (?:her|his|their) being\b",
    r"\bsomething about the way\b",
    r"\bin that moment\b",
    r"\bcomplicated, layered\b",
    r"\bunspoken words\b",
    r"\bchest tighten\b",
    r"\bnot just [^.!?]+\.\s+It was\b",
)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


class VoiceConsistencyMetric(BaseMetric):  # type: ignore[no-untyped-call]
    """Score prose for voice consistency.

    The Phase 14 slice defaults to a deterministic heuristic so CI and local
    runs never require a live Anthropic API call. Claude judging remains
    available by passing use_llm_judge=True or setting FF_EVAL_USE_LLM=true.
    """

    def __init__(
        self,
        threshold: float = 0.75,
        model_tier: str = "test",
        use_llm_judge: bool | None = None,
    ) -> None:
        self.threshold = threshold
        self.model_tier = model_tier
        self.use_llm_judge = (
            _env_flag("FF_EVAL_USE_LLM") if use_llm_judge is None else use_llm_judge
        )
        self.score: float = 0.0
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase) -> float:
        """Score prose for voice consistency."""
        prose = test_case.actual_output or ""
        if not self.use_llm_judge:
            self.score, self.reason = _deterministic_voice_score(prose)
            return self.score

        self.score, self.reason = self._measure_with_llm(prose)
        return self.score

    def _measure_with_llm(self, prose: str) -> tuple[float, str]:
        model = _TEST_MODEL if self.model_tier == "test" else _PROD_MODEL
        prompt = _PROMPT_TEMPLATE.format(prose=prose[:2000])

        try:
            import anthropic  # noqa: PLC0415

            client = anthropic.Anthropic()
            response = client.messages.create(
                model=model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            block = response.content[0]
            raw = str(getattr(block, "text", ""))
            result = json.loads(_strip_json_fence(raw))
            score = _clamp(float(result["score"]))
            return score, str(result["rationale"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("VoiceConsistencyMetric LLM evaluation failed: %s", exc)
            score, reason = _deterministic_voice_score(prose)
            return score, f"LLM evaluation failed; {reason}"

    async def a_measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        """Async wrapper - delegates to synchronous measure()."""
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.score >= self.threshold

    @property
    def name(self) -> str:
        return "VoiceConsistencyMetric"


def _deterministic_voice_score(prose: str) -> tuple[float, str]:
    words = re.findall(r"\b\w+(?:'\w+)?\b", prose)
    word_count = len(words)
    if word_count == 0:
        return 0.0, "empty prose"

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prose.strip()) if s.strip()]
    sentence_lengths = [len(re.findall(r"\b\w+(?:'\w+)?\b", sentence)) for sentence in sentences]

    score = 0.72
    if word_count >= 200:
        score += 0.08
    elif word_count >= 50:
        score += 0.04

    avg_sentence_length = statistics.fmean(sentence_lengths) if sentence_lengths else 0.0
    if 8.0 <= avg_sentence_length <= 28.0:
        score += 0.05

    if len(sentence_lengths) >= 4 and statistics.pstdev(sentence_lengths) >= 4.0:
        score += 0.04

    if re.search(r'"[^"\n]+"', prose):
        score += 0.04

    paragraph_count = len([p for p in re.split(r"\n\s*\n", prose) if p.strip()])
    if paragraph_count >= 3:
        score += 0.03

    structural_weight, structural_penalty = _structural_penalty(prose, word_count)
    marker_count = sum(
        len(re.findall(pattern, prose, flags=re.IGNORECASE)) for pattern in _VOICE_TELL_PATTERNS
    )
    marker_penalty = min(0.12, marker_count * 0.015)

    score = _clamp(score - structural_penalty - marker_penalty)
    reason = (
        "deterministic heuristic: "
        f"words={word_count}, structural_weight={structural_weight}, "
        f"voice_tell_markers={marker_count}"
    )
    return round(score, 4), reason


def _structural_penalty(prose: str, word_count: int) -> tuple[int, float]:
    try:
        from pipeline.agents.structural_analysis import StructuralAnalyzer  # noqa: PLC0415

        report = StructuralAnalyzer().analyze(prose)
        weighted = report.weighted_score()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Voice structural fallback used: %s", exc)
        weighted = _fallback_structural_weight(prose)

    density = weighted / max(1.0, word_count / 1000.0)
    return weighted, min(0.20, density * 0.01)


def _fallback_structural_weight(prose: str) -> int:
    weighted = 0
    if re.search(r"\bIt(?:'s| is) not [^.!?]+\.\s+It(?:'s| is)\b", prose, re.IGNORECASE):
        weighted += 2
    if re.search(r"\bNot because [^.!?]+\.\s+Because\b", prose, re.IGNORECASE):
        weighted += 2
    weighted += prose.count("...")
    weighted += prose.count("...")
    if prose.count("-") > 8:
        weighted += 1
    return weighted


def _strip_json_fence(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
