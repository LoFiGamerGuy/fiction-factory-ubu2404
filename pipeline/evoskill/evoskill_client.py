"""EvoSkillClient — wraps EvoSkill Proposer/Evaluator/Frontier API."""

from __future__ import annotations

import os
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

from pipeline.evoskill.trace_collector import Trace

# If Claude Managed Agents 'Dreaming' feature reaches GA and produces better
# per-series improvements than EvoSkill nightly pass, flip USE_DREAMING = True
# and implement _dreaming_propose_skill() below. See docs/v2-roadmap.md §V2.9.
USE_DREAMING = False


@dataclass
class CandidateSkill:
    """A proposed skill candidate from the EvoSkill Proposer."""

    skill_id: str
    series_id: str
    condition: str
    recommendation: str
    failure_mode: str | None
    proposed_at: str
    score: float = 0.0


@dataclass
class EvalResult:
    """Evaluation result for a candidate skill against a benchmark corpus."""

    skill_id: str
    score: float
    baseline_score: float
    improvement: float
    passed: bool


class EvoSkillClient:
    """Client for the EvoSkill Proposer / Evaluator / Frontier API.

    In V1, when ``api_url`` is not configured, all methods operate in local
    mock mode and never make network requests.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._api_url = api_url or os.environ.get("EVOSKILL_API_URL")
        self._api_key = api_key or os.environ.get("EVOSKILL_API_KEY")

    # ── Public API ────────────────────────────────────────────────────────────

    def propose_skill(
        self,
        failure_traces: list[Trace],
        series_id: str,
    ) -> CandidateSkill:
        """Propose a new skill from a batch of failure traces.

        Remote mode: POST /propose with trace summaries.
        Local mock: synthesise a stub skill from the dominant failure_mode.
        """
        if USE_DREAMING:
            return self._dreaming_propose_skill(failure_traces, series_id)

        if self._api_url:
            return self._remote_propose(failure_traces, series_id)

        return self._stub_propose(failure_traces, series_id)

    def evaluate_skill(
        self,
        candidate: CandidateSkill,
        benchmark_corpus: list[Trace],
    ) -> EvalResult:
        """Evaluate a candidate skill against a benchmark corpus.

        Remote mode: POST /evaluate.
        Local mock: return a fixed passing result.
        """
        if self._api_url:
            return self._remote_evaluate(candidate, benchmark_corpus)

        return EvalResult(
            skill_id=candidate.skill_id,
            score=0.7,
            baseline_score=0.5,
            improvement=0.2,
            passed=True,
        )

    def update_frontier(
        self,
        candidate: CandidateSkill,
        eval_result: EvalResult,
    ) -> bool:
        """Promote a skill to the frontier if it improves on baseline.

        Remote mode: POST /frontier.
        Local mock: return True when improvement > 0.
        """
        if self._api_url:
            return self._remote_update_frontier(candidate, eval_result)

        return eval_result.improvement > 0

    # ── Dreaming stub ─────────────────────────────────────────────────────────

    def _dreaming_propose_skill(
        self,
        failure_traces: list[Trace],
        series_id: str,
    ) -> CandidateSkill:
        """Stub: raise until Claude Dreaming reaches GA.

        See docs/v2-roadmap.md §V2.9 for the planned implementation.
        """
        raise NotImplementedError("Claude Dreaming not GA; USE_DREAMING=False")

    # ── Remote helpers ────────────────────────────────────────────────────────

    def _remote_propose(
        self,
        failure_traces: list[Trace],
        series_id: str,
    ) -> CandidateSkill:
        import json
        import urllib.request

        payload = {
            "series_id": series_id,
            "failure_traces": [
                {
                    "trace_id": t.trace_id,
                    "failure_mode": t.failure_mode,
                    "routing_decisions": t.routing_decisions,
                    "quality_scores": t.quality_scores,
                }
                for t in failure_traces
            ],
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self._api_url}/propose",
            data=body,
            headers=self._auth_headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            data: dict[str, Any] = json.loads(resp.read())

        return CandidateSkill(
            skill_id=data["skill_id"],
            series_id=series_id,
            condition=data["condition"],
            recommendation=data["recommendation"],
            failure_mode=data.get("failure_mode"),
            proposed_at=data["proposed_at"],
            score=float(data.get("score", 0.0)),
        )

    def _remote_evaluate(
        self,
        candidate: CandidateSkill,
        benchmark_corpus: list[Trace],
    ) -> EvalResult:
        import json
        import urllib.request

        payload = {
            "skill_id": candidate.skill_id,
            "series_id": candidate.series_id,
            "condition": candidate.condition,
            "recommendation": candidate.recommendation,
            "benchmark_trace_ids": [t.trace_id for t in benchmark_corpus],
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self._api_url}/evaluate",
            data=body,
            headers=self._auth_headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            data: dict[str, Any] = json.loads(resp.read())

        score = float(data["score"])
        baseline = float(data["baseline_score"])
        return EvalResult(
            skill_id=candidate.skill_id,
            score=score,
            baseline_score=baseline,
            improvement=score - baseline,
            passed=bool(data.get("passed", score > baseline)),
        )

    def _remote_update_frontier(
        self,
        candidate: CandidateSkill,
        eval_result: EvalResult,
    ) -> bool:
        import json
        import urllib.request

        payload = {
            "skill_id": candidate.skill_id,
            "series_id": candidate.series_id,
            "score": eval_result.score,
            "improvement": eval_result.improvement,
            "passed": eval_result.passed,
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self._api_url}/frontier",
            data=body,
            headers=self._auth_headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            data: dict[str, Any] = json.loads(resp.read())

        return bool(data.get("kept", False))

    # ── Stub / mock helpers ───────────────────────────────────────────────────

    @staticmethod
    def _stub_propose(
        failure_traces: list[Trace],
        series_id: str,
    ) -> CandidateSkill:
        """Generate a deterministic stub skill from dominant failure_mode counts."""
        from datetime import UTC, datetime

        mode_counts: Counter[str] = Counter()
        for t in failure_traces:
            if t.failure_mode:
                mode_counts[t.failure_mode] += 1

        dominant_mode: str | None = mode_counts.most_common(1)[0][0] if mode_counts else None

        condition_map: dict[str | None, str] = {
            "quality_gate_fail": "quality score below threshold after revision",
            "continuity_error": "bible contradiction detected in scene output",
            "pacing_violation": "overdue story promises not resolved",
            "voice_drift": "voice consistency score below target",
            "heat_curve_miss": "heat level deviates from escalation curve",
            None: "repeated scene failures with no dominant mode",
        }
        recommendation_map: dict[str | None, str] = {
            "quality_gate_fail": "add an explicit quality pre-check before writer agent invocation",
            "continuity_error": "inject bible summary into writer context window",
            "pacing_violation": "surface overdue promises in scene brief",
            "voice_drift": "include voice exemplar in writer prompt",
            "heat_curve_miss": "enforce heat_level cap in quality agent",
            None: "review routing logic for repeated failure patterns",
        }

        return CandidateSkill(
            skill_id=str(uuid.uuid4()),
            series_id=series_id,
            condition=condition_map.get(dominant_mode, condition_map[None]),
            recommendation=recommendation_map.get(dominant_mode, recommendation_map[None]),
            failure_mode=dominant_mode,
            proposed_at=datetime.now(UTC).isoformat(),
            score=0.0,
        )

    def _auth_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers
