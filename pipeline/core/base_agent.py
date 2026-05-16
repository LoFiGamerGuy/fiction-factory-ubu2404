"""BaseAgent — abstract base class for all pipeline agents.

Every agent inherits from BaseAgent and declares:
  - ``impl_class``: one of "deterministic" / "llm" / "hybrid" (class-level)
  - ``version``: semver string (class-level)
  - ``_execute(job_context)``: the agent's implementation (abstract)

Calling ``run()`` logs the invocation and delegates to ``_execute()``.
All log entries are structured JSON appended to AgentContext.log_path.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import ClassVar

from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext

logger = logging.getLogger(__name__)

_VALID_IMPL_CLASSES: frozenset[str] = frozenset({"deterministic", "llm", "hybrid"})


class BaseAgent(ABC):
    """Abstract base for all pipeline agents.

    Subclasses **must** declare ``impl_class`` and ``version`` as class
    attributes.  Missing or invalid ``impl_class`` raises ``TypeError`` at
    instantiation time (fail-fast, DEC-008).
    """

    impl_class: ClassVar[str]
    version: ClassVar[str]

    def __init__(self, ctx: AgentContext) -> None:
        cls = type(self)
        ic = getattr(cls, "impl_class", None)
        if ic is None:
            raise TypeError(
                f"{cls.__name__} must declare impl_class as one of {sorted(_VALID_IMPL_CLASSES)}"
            )
        if ic not in _VALID_IMPL_CLASSES:
            raise TypeError(
                f"{cls.__name__}.impl_class={ic!r} is invalid; "
                f"must be one of {sorted(_VALID_IMPL_CLASSES)}"
            )
        self.ctx = ctx

    # ── Public contract ───────────────────────────────────────────────────────

    def run(self, job_context: JobContext) -> JobContext:
        """Execute the agent, log the call, and return the updated JobContext."""
        start = time.monotonic()
        input_hash = _hash_dict({"job_id": job_context.job_id, "scene_id": job_context.scene_id})

        result = self._execute(job_context)

        duration_ms = (time.monotonic() - start) * 1000
        output_hash = _hash_dict(result.output_data)
        model_version = ""
        if type(self).impl_class in ("llm", "hybrid"):
            model_version = self.ctx.model_tier

        self._emit_run_log(
            job_context=job_context,
            input_hash=input_hash,
            output_hash=output_hash,
            duration_ms=duration_ms,
            model_version=model_version,
        )
        return result

    @abstractmethod
    def _execute(self, job_context: JobContext) -> JobContext:
        """Agent implementation. Override in every concrete subclass."""

    # ── Logging ───────────────────────────────────────────────────────────────

    def _emit_run_log(
        self,
        job_context: JobContext,
        input_hash: str,
        output_hash: str,
        duration_ms: float,
        model_version: str = "",
    ) -> None:
        entry: dict[str, object] = {
            "component_id": type(self).__name__,
            "version": getattr(type(self), "version", "unknown"),
            "impl_class": type(self).impl_class,
            "job_id": job_context.job_id,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "duration_ms": round(duration_ms, 1),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if model_version:
            entry["model_version"] = model_version

        try:
            with self.ctx.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError as exc:
            logger.warning("Agent log write failed (non-fatal): %s", exc)


# ── Helper ────────────────────────────────────────────────────────────────────


def _hash_dict(d: object) -> str:
    serialised = json.dumps(d, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode()).hexdigest()[:12]
