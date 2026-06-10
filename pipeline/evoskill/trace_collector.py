"""TraceCollector — collects scene traces for EvoSkill learning."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pipeline.core.job_context import JobContext


@dataclass
class Trace:
    """A single scene execution trace for EvoSkill learning."""

    trace_id: str
    series_id: str
    book_id: str
    scene_id: str
    trace_type: Literal["failure", "success"]
    failure_mode: str | None
    agent_inputs: dict[str, str]
    agent_outputs: dict[str, str]
    routing_decisions: list[str]
    quality_scores: dict[str, float]
    critic_scores: dict[str, float]
    word_count: int
    timestamp: str


class TraceCollector:
    """Collects and persists scene execution traces for EvoSkill learning."""

    def __init__(self, data_root: Path = Path("data"), score_threshold: float = 0.7) -> None:
        self._data_root = data_root
        self._score_threshold = score_threshold

    # ── Public API ────────────────────────────────────────────────────────────

    def collect_scene_trace(
        self,
        job_context: JobContext,
        routing_decisions: list[str],
        quality_scores: dict[str, float] | None = None,
        critic_scores: dict[str, float] | None = None,
    ) -> Trace:
        """Build and return a Trace from a completed scene job.

        Classification priority (highest wins):
          1. bible_contradiction → failure / continuity_error
          2. overdue_promises   → failure / pacing_violation
          3. routing REVISE or RE_PLAN in decisions → failure / quality_gate_fail
          4. Otherwise          → success
        """
        trace_type: Literal["failure", "success"]
        failure_mode: str | None

        quality_score_map = dict(quality_scores) if quality_scores else {}
        critic_score_map = dict(critic_scores) if critic_scores else {}

        if job_context.bible_contradiction:
            trace_type = "failure"
            failure_mode = "continuity_error"
        elif job_context.overdue_promises:
            trace_type = "failure"
            failure_mode = "pacing_violation"
        elif self._has_score_failure(quality_score_map, critic_score_map):
            trace_type = "failure"
            failure_mode = "quality_gate_fail"
        elif any(d in ("REVISE", "RE_PLAN") for d in routing_decisions):
            trace_type = "failure"
            failure_mode = "quality_gate_fail"
        else:
            trace_type = "success"
            failure_mode = None

        agent_inputs = self._build_input_hashes(job_context)
        agent_outputs = self._build_output_hashes(job_context)
        word_count = len(job_context.final_text.split()) if job_context.final_text else 0

        return Trace(
            trace_id=str(uuid.uuid4()),
            series_id=job_context.series_id,
            book_id=job_context.book_id,
            scene_id=job_context.scene_id,
            trace_type=trace_type,
            failure_mode=failure_mode,
            agent_inputs=agent_inputs,
            agent_outputs=agent_outputs,
            routing_decisions=list(routing_decisions),
            quality_scores=quality_score_map,
            critic_scores=critic_score_map,
            word_count=word_count,
            timestamp=datetime.now(UTC).isoformat(),
        )

    def save_trace(self, trace: Trace) -> None:
        """Persist a trace to ``data/{series_id}/traces/{scene_id}.json``."""
        dest = self._data_root / trace.series_id / "traces" / f"{trace.scene_id}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = self._trace_to_dict(trace)
        dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_failure_traces(
        self,
        series_id: str,
        since: datetime | None = None,
    ) -> list[Trace]:
        """Return all failure traces for a series, optionally filtered by timestamp.

        Reads every ``*.json`` file under ``data/{series_id}/traces/``.
        """
        traces_dir = self._data_root / series_id / "traces"
        if not traces_dir.is_dir():
            return []

        results: list[Trace] = []
        for path in sorted(traces_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                trace = self._dict_to_trace(raw)
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

            if trace.trace_type != "failure":
                continue

            if since is not None:
                ts = datetime.fromisoformat(trace.timestamp)
                if ts < since:
                    continue

            results.append(trace)

        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_input_hashes(self, job_context: JobContext) -> dict[str, str]:
        """Return {agent_id: sha256[:16]} for each entry in output_data.

        We hash the full agent payload to represent its input fingerprint
        (the pipeline's output_data accumulates agent outputs sequentially,
        so the hash of each entry serves as the input provenance digest).
        """
        result: dict[str, str] = {}
        for agent_id, data in job_context.output_data.items():
            serialised = json.dumps(data, sort_keys=True, default=str)
            result[agent_id] = hashlib.sha256(serialised.encode()).hexdigest()[:16]
        return result

    def _build_output_hashes(self, job_context: JobContext) -> dict[str, str]:
        """Return {agent_id: sha256[:16]} for each entry in output_data."""
        return self._build_input_hashes(job_context)

    def _has_score_failure(
        self,
        quality_scores: dict[str, float],
        critic_scores: dict[str, float],
    ) -> bool:
        for scores in (quality_scores, critic_scores):
            for key, value in scores.items():
                if key == "needs_review" and value >= 1.0:
                    return True
                if key == "needs_review":
                    continue
                if key.endswith("_score") or key in {"score", "quality", "voice", "ai_tell"}:
                    if value < self._score_threshold:
                        return True
        return False

    @staticmethod
    def _trace_to_dict(trace: Trace) -> dict[str, object]:
        return {
            "trace_id": trace.trace_id,
            "series_id": trace.series_id,
            "book_id": trace.book_id,
            "scene_id": trace.scene_id,
            "trace_type": trace.trace_type,
            "failure_mode": trace.failure_mode,
            "agent_inputs": trace.agent_inputs,
            "agent_outputs": trace.agent_outputs,
            "routing_decisions": trace.routing_decisions,
            "quality_scores": trace.quality_scores,
            "critic_scores": trace.critic_scores,
            "word_count": trace.word_count,
            "timestamp": trace.timestamp,
        }

    @staticmethod
    def _dict_to_trace(raw: dict[str, Any]) -> Trace:
        return Trace(
            trace_id=str(raw["trace_id"]),
            series_id=str(raw["series_id"]),
            book_id=str(raw["book_id"]),
            scene_id=str(raw["scene_id"]),
            trace_type="failure" if str(raw["trace_type"]) == "failure" else "success",
            failure_mode=str(raw["failure_mode"]) if raw.get("failure_mode") else None,
            agent_inputs={str(k): str(v) for k, v in (raw.get("agent_inputs") or {}).items()},
            agent_outputs={str(k): str(v) for k, v in (raw.get("agent_outputs") or {}).items()},
            routing_decisions=[str(d) for d in (raw.get("routing_decisions") or [])],
            quality_scores={str(k): float(v) for k, v in (raw.get("quality_scores") or {}).items()},
            critic_scores={str(k): float(v) for k, v in (raw.get("critic_scores") or {}).items()},
            word_count=int(raw.get("word_count") or 0),
            timestamp=str(raw["timestamp"]),
        )
