"""JobContext — typed dataclass for all inter-agent job passing.

Replaces plain dict threading through the pipeline (MBSE B3 fix).
Every agent receives a JobContext in and returns a JobContext with output appended.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from pipeline.profiles.project_spec import ProjectSpec


@dataclass
class JobContext:
    """Typed job descriptor passed between every agent in the pipeline.

    ``input_hash`` is a SHA-256 digest of the inputs that produced this job,
    used for provenance and deduplication. ``output_data`` accumulates agent
    outputs as the job moves through the pipeline.
    """

    job_id: str
    series_id: str
    book_id: str
    chapter_id: int
    scene_id: str
    spec: ProjectSpec
    model_tier: str = "test"
    seed: int = 0
    run_timestamp: str = ""
    input_hash: str = ""
    output_data: dict[str, Any] = field(default_factory=dict)

    def with_output(self, agent_id: str, data: dict[str, Any]) -> JobContext:
        """Return a copy with agent output appended (non-mutating)."""
        import dataclasses

        new_output = {**self.output_data, agent_id: data}
        return dataclasses.replace(self, output_data=new_output)

    @staticmethod
    def compute_hash(data: dict[str, Any]) -> str:
        """Compute a stable SHA-256 hex digest of a JSON-serialisable dict."""
        serialised = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialised.encode()).hexdigest()[:16]
