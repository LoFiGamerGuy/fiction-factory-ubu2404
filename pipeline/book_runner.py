"""BookRunner — ordered book-level execution over the existing JobRunner path.

This is intentionally thin: scene generation remains owned by ``JobRunner``.
BookRunner supplies ordered scene iteration and durable per-scene status records
so interrupted full-book runs have enough information to resume safely later.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pipeline.book_structure_planner import SceneInventory, SceneSlot
from pipeline.core.agent_context import AgentContext
from pipeline.core.job_context import JobContext
from pipeline.core.model_router import ModelRouter
from pipeline.job_runner import JobRunner, SceneRunResult
from pipeline.profiles.project_spec import ProjectSpec

logger = logging.getLogger(__name__)


class SceneJobRunner(Protocol):
    """Minimal protocol required from JobRunner or a test fake."""

    def run_scene(self, job_context: JobContext) -> SceneRunResult:
        """Run one scene and return its final scene result."""
        ...


@dataclass(frozen=True)
class BookScene:
    """Scene input for ordered book execution."""

    scene_id: str
    chapter_id: int
    scene_brief: str
    word_count_target: int
    heat_level: int
    scene_function: str = "scene"
    act: int = 0
    scene_number: int = 0
    required_slot_id: str | None = None

    @classmethod
    def from_slot(cls, slot: SceneSlot, scene_brief: str | None = None) -> BookScene:
        """Create a runnable scene from a planned inventory slot."""
        brief = scene_brief or (
            f"Write {slot.scene_function} for {slot.scene_id} in chapter {slot.chapter}."
        )
        return cls(
            scene_id=slot.scene_id,
            chapter_id=slot.chapter,
            scene_brief=brief,
            word_count_target=slot.word_count_target,
            heat_level=slot.heat_level_target,
            scene_function=slot.scene_function,
            act=slot.act,
            scene_number=slot.scene_number,
            required_slot_id=slot.required_slot_id,
        )


@dataclass(frozen=True)
class BookSceneStatus:
    """Durable per-scene execution status for future resume support."""

    scene_id: str
    chapter_id: int
    job_id: str
    thread_id: str
    status: str
    output_path: str
    convergence_decision: str
    revise_count: int
    force_resolved: bool
    word_count: int
    elapsed_seconds: float
    started_at: str
    completed_at: str
    error: str

    @property
    def successful(self) -> bool:
        return self.status in {"completed", "skipped"} and self.error == ""

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> BookSceneStatus:
        return cls(
            scene_id=str(raw.get("scene_id", "")),
            chapter_id=int(raw.get("chapter_id", 0)),
            job_id=str(raw.get("job_id", "")),
            thread_id=str(raw.get("thread_id", "")),
            status=str(raw.get("status", "")),
            output_path=str(raw.get("output_path", "")),
            convergence_decision=str(raw.get("convergence_decision", "")),
            revise_count=int(raw.get("revise_count", 0)),
            force_resolved=bool(raw.get("force_resolved", False)),
            word_count=int(raw.get("word_count", 0)),
            elapsed_seconds=float(raw.get("elapsed_seconds", 0.0)),
            started_at=str(raw.get("started_at", "")),
            completed_at=str(raw.get("completed_at", "")),
            error=str(raw.get("error", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "chapter_id": self.chapter_id,
            "job_id": self.job_id,
            "thread_id": self.thread_id,
            "status": self.status,
            "output_path": self.output_path,
            "convergence_decision": self.convergence_decision,
            "revise_count": self.revise_count,
            "force_resolved": self.force_resolved,
            "word_count": self.word_count,
            "elapsed_seconds": self.elapsed_seconds,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


@dataclass(frozen=True)
class BookRunResult:
    """Summary of one ordered book run."""

    run_id: str
    book_id: str
    series_id: str
    model_tier: str
    planned_scene_count: int
    attempted_scene_count: int
    successful_scenes: int
    failed_scenes: int
    go_scenes: int
    force_resolved_scenes: int
    skipped_scenes: int
    previous_failed_scene_ids: list[str]
    elapsed_seconds: float
    status_path: str
    scenes: list[BookSceneStatus]

    @property
    def passed(self) -> bool:
        return (
            self.attempted_scene_count == self.planned_scene_count
            and self.failed_scenes == 0
            and self.successful_scenes == self.planned_scene_count
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "book_id": self.book_id,
            "series_id": self.series_id,
            "model_tier": self.model_tier,
            "planned_scene_count": self.planned_scene_count,
            "attempted_scene_count": self.attempted_scene_count,
            "successful_scenes": self.successful_scenes,
            "failed_scenes": self.failed_scenes,
            "go_scenes": self.go_scenes,
            "force_resolved_scenes": self.force_resolved_scenes,
            "skipped_scenes": self.skipped_scenes,
            "previous_failed_scene_ids": self.previous_failed_scene_ids,
            "elapsed_seconds": self.elapsed_seconds,
            "status_path": self.status_path,
            "passed": self.passed,
            "scenes": [scene.to_dict() for scene in self.scenes],
        }


@dataclass(frozen=True)
class ManuscriptAssemblyResult:
    """Result of ordered manuscript assembly from finalized scene files."""

    manuscript_path: str
    scene_count: int
    word_count: int
    scene_paths: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manuscript_path": self.manuscript_path,
            "scene_count": self.scene_count,
            "word_count": self.word_count,
            "scene_paths": self.scene_paths,
        }


def scenes_from_inventory(
    inventory: SceneInventory,
    scene_briefs: Mapping[str, str] | None = None,
) -> list[BookScene]:
    """Convert a persisted/planned SceneInventory into runnable BookScene inputs."""
    briefs = scene_briefs or {}
    return [
        BookScene.from_slot(slot, scene_brief=briefs.get(slot.scene_id))
        for slot in inventory.scenes
    ]


class BookRunner:
    """Runs every scene in a book through the existing single-scene JobRunner."""

    def __init__(
        self,
        *,
        agent_ctx: AgentContext,
        model_router: ModelRouter | None = None,
        job_runner: SceneJobRunner | None = None,
        max_revisions: int = 3,
        checkpoint_db_path: Path | str | None = None,
        status_path: Path | None = None,
    ) -> None:
        if job_runner is None and model_router is None:
            raise ValueError("BookRunner requires model_router unless job_runner is supplied")

        self._ctx = agent_ctx
        if job_runner is not None:
            self._job_runner = job_runner
        else:
            if model_router is None:
                raise ValueError("BookRunner requires model_router unless job_runner is supplied")
            self._job_runner = JobRunner(
                agent_ctx=agent_ctx,
                model_router=model_router,
                max_revisions=max_revisions,
                checkpoint_db_path=str(checkpoint_db_path) if checkpoint_db_path else None,
            )
        self._status_path = (
            status_path or agent_ctx.project_layout.book_dir() / "book_run_status.jsonl"
        )

    @property
    def status_path(self) -> Path:
        return self._status_path

    def run_inventory(
        self,
        *,
        run_id: str,
        spec: ProjectSpec,
        inventory: SceneInventory,
        scene_briefs: Mapping[str, str] | None = None,
        base_seed: int = 0,
        stop_on_error: bool = True,
        resume: bool = True,
        force: bool = False,
        reset_status: bool | None = None,
    ) -> BookRunResult:
        """Run all scenes from a SceneInventory in inventory order."""
        return self.run_book(
            run_id=run_id,
            spec=spec,
            scenes=scenes_from_inventory(inventory, scene_briefs=scene_briefs),
            base_seed=base_seed,
            stop_on_error=stop_on_error,
            resume=resume,
            force=force,
            reset_status=reset_status,
        )

    def run_book(
        self,
        *,
        run_id: str,
        spec: ProjectSpec,
        scenes: Sequence[BookScene],
        base_seed: int = 0,
        stop_on_error: bool = True,
        resume: bool = True,
        force: bool = False,
        reset_status: bool | None = None,
    ) -> BookRunResult:
        """Run scenes in order and append one status record per attempted scene."""
        started = time.monotonic()
        should_reset_status = force if reset_status is None else reset_status
        history = [] if should_reset_status else self._read_status_history()
        latest_by_scene = {record.scene_id: record for record in history}
        previous_failed_scene_ids = _unique_scene_ids(
            record.scene_id for record in history if not record.successful
        )
        if should_reset_status and self._status_path.exists():
            self._status_path.unlink()

        records: list[BookSceneStatus] = []
        for index, scene in enumerate(scenes, start=1):
            logger.info("BookRunner: running scene %d/%d: %s", index, len(scenes), scene.scene_id)
            prior_status = latest_by_scene.get(scene.scene_id)
            if resume and not force and self._can_skip_scene(scene, prior_status):
                record = self._make_skipped_status(run_id=run_id, scene=scene, prior=prior_status)
            else:
                record = self._run_one_scene(
                    run_id=run_id,
                    spec=spec,
                    scene=scene,
                    seed=base_seed + index,
                )
            records.append(record)
            self._append_status(record)
            if stop_on_error and not record.successful:
                break

        elapsed = round(time.monotonic() - started, 3)
        return BookRunResult(
            run_id=run_id,
            book_id=spec.book_id,
            series_id=spec.series_id,
            model_tier=self._ctx.model_tier,
            planned_scene_count=len(scenes),
            attempted_scene_count=len(records),
            successful_scenes=sum(1 for record in records if record.successful),
            failed_scenes=sum(1 for record in records if not record.successful),
            go_scenes=sum(1 for record in records if record.convergence_decision == "GO"),
            force_resolved_scenes=sum(1 for record in records if record.force_resolved),
            skipped_scenes=sum(1 for record in records if record.status == "skipped"),
            previous_failed_scene_ids=previous_failed_scene_ids,
            elapsed_seconds=elapsed,
            status_path=str(self._status_path),
            scenes=records,
        )

    def assemble_manuscript(
        self,
        scenes: Sequence[BookScene],
        manuscript_path: Path | None = None,
    ) -> ManuscriptAssemblyResult:
        """Assemble finalized scene files into manuscript.md in scene order."""
        target_path = manuscript_path or self._ctx.project_layout.manuscript_path()
        book_id = str(self._ctx.project_layout.book_id)
        parts: list[str] = [f"# {book_id}"]
        scene_paths: list[str] = []
        total_words = 0
        current_chapter: int | None = None

        for scene in scenes:
            scene_path = self._ctx.project_layout.scene_output_path(
                scene.chapter_id,
                scene.scene_id,
            )
            if not scene_path.exists():
                raise FileNotFoundError(
                    f"Missing finalized scene file for {scene.scene_id}: {scene_path}"
                )

            text = scene_path.read_text(encoding="utf-8").strip()
            total_words += len(text.split())
            scene_paths.append(str(scene_path))

            if scene.chapter_id != current_chapter:
                parts.append(f"## Chapter {scene.chapter_id}")
                current_chapter = scene.chapter_id
            parts.append(f"### Scene {scene.scene_id}")
            parts.append(text)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("\n\n".join(parts).rstrip() + "\n", encoding="utf-8")
        return ManuscriptAssemblyResult(
            manuscript_path=str(target_path),
            scene_count=len(scenes),
            word_count=total_words,
            scene_paths=scene_paths,
        )

    def write_book_run_summary(
        self,
        *,
        result: BookRunResult,
        provider: str,
        manuscript: ManuscriptAssemblyResult | None = None,
        eval_status: Mapping[str, Any] | None = None,
        verifier_status: Mapping[str, Any] | None = None,
        draft_acceptance_status: Mapping[str, Any] | None = None,
        cost_log_path: Path | None = None,
        extra_metadata: Mapping[str, Any] | None = None,
        summary_path: Path | None = None,
    ) -> dict[str, Any]:
        """Write durable book_run_summary.json for a completed or attempted book run."""
        target_path = summary_path or self._ctx.project_layout.book_dir() / "book_run_summary.json"
        last_scene_id = result.scenes[-1].scene_id if result.scenes else ""
        dashboard = asdict(
            self._ctx.ledger_manager.get_dashboard_summary(result.book_id, last_scene_id)
        )
        failed_scene_ids = [record.scene_id for record in result.scenes if not record.successful]
        total_word_count = (
            manuscript.word_count
            if manuscript is not None
            else sum(record.word_count for record in result.scenes)
        )

        payload = result.to_dict()
        payload.update(
            {
                "provider": provider,
                "scene_dir": str(self._ctx.project_layout.book_dir() / "scenes"),
                "manuscript_path": (
                    manuscript.manuscript_path
                    if manuscript is not None
                    else str(self._ctx.project_layout.manuscript_path())
                ),
                "total_word_count": total_word_count,
                "assembled_scene_count": manuscript.scene_count if manuscript is not None else 0,
                "failed_scene_ids": failed_scene_ids,
                "checkpoint_thread_ids": {
                    record.scene_id: record.thread_id for record in result.scenes
                },
                "ledger_dashboard_summary": dashboard,
                "cost_summary": _summarize_cost_log(
                    cost_log_path or self._ctx.project_layout.cost_log_path()
                ),
                "files_api": {
                    "enabled": self._ctx.managed_agent_config.files_api_enabled,
                    "uploaded_file_ids": dict(self._ctx.managed_agent_config.uploaded_file_ids),
                },
                "eval_status": dict(eval_status) if eval_status is not None else None,
                "verifier_status": dict(verifier_status) if verifier_status is not None else None,
                "draft_acceptance_status": (
                    dict(draft_acceptance_status) if draft_acceptance_status is not None else None
                ),
                "summary_path": str(target_path),
            }
        )
        if extra_metadata is not None:
            payload.update(dict(extra_metadata))

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload

    def _run_one_scene(
        self,
        *,
        run_id: str,
        spec: ProjectSpec,
        scene: BookScene,
        seed: int,
    ) -> BookSceneStatus:
        scene_started = time.monotonic()
        started_at = _utc_now()
        output_path = self._ctx.project_layout.scene_output_path(scene.chapter_id, scene.scene_id)
        job_id = f"{run_id}_{scene.scene_id}"
        job_context = JobContext(
            job_id=job_id,
            series_id=spec.series_id,
            book_id=spec.book_id,
            chapter_id=scene.chapter_id,
            scene_id=scene.scene_id,
            spec=spec,
            model_tier=self._ctx.model_tier,
            seed=seed,
            scene_brief=scene.scene_brief,
            word_count_target=scene.word_count_target,
            heat_level=scene.heat_level,
        )

        try:
            result = self._job_runner.run_scene(job_context)
            final_text = result.final_text or ""
            error = result.error or ""
            status = "completed" if error == "" else "error"
            return BookSceneStatus(
                scene_id=scene.scene_id,
                chapter_id=scene.chapter_id,
                job_id=job_id,
                thread_id=result.thread_id,
                status=status,
                output_path=str(output_path),
                convergence_decision=result.convergence_decision,
                revise_count=result.revise_count,
                force_resolved=result.force_resolved,
                word_count=len(final_text.split()),
                elapsed_seconds=round(time.monotonic() - scene_started, 3),
                started_at=started_at,
                completed_at=_utc_now(),
                error=error,
            )
        except Exception as exc:
            return BookSceneStatus(
                scene_id=scene.scene_id,
                chapter_id=scene.chapter_id,
                job_id=job_id,
                thread_id="",
                status="error",
                output_path=str(output_path),
                convergence_decision="",
                revise_count=0,
                force_resolved=False,
                word_count=0,
                elapsed_seconds=round(time.monotonic() - scene_started, 3),
                started_at=started_at,
                completed_at=_utc_now(),
                error=str(exc),
            )

    def _append_status(self, record: BookSceneStatus) -> None:
        self._status_path.parent.mkdir(parents=True, exist_ok=True)
        with self._status_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")

    def _read_status_history(self) -> list[BookSceneStatus]:
        if not self._status_path.exists():
            return []
        records: list[BookSceneStatus] = []
        for line in self._status_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(BookSceneStatus.from_dict(json.loads(line)))
        return records

    def _can_skip_scene(
        self,
        scene: BookScene,
        prior: BookSceneStatus | None,
    ) -> bool:
        if prior is None or not prior.successful:
            return False
        scene_path = Path(
            self._ctx.project_layout.scene_output_path(scene.chapter_id, scene.scene_id)
        )
        return scene_path.exists()

    def _make_skipped_status(
        self,
        *,
        run_id: str,
        scene: BookScene,
        prior: BookSceneStatus | None,
    ) -> BookSceneStatus:
        if prior is None:
            raise ValueError(f"Cannot skip {scene.scene_id}: prior status missing")
        now = _utc_now()
        output_path = self._ctx.project_layout.scene_output_path(scene.chapter_id, scene.scene_id)
        return BookSceneStatus(
            scene_id=scene.scene_id,
            chapter_id=scene.chapter_id,
            job_id=f"{run_id}_{scene.scene_id}",
            thread_id=prior.thread_id,
            status="skipped",
            output_path=str(output_path),
            convergence_decision=prior.convergence_decision,
            revise_count=prior.revise_count,
            force_resolved=prior.force_resolved,
            word_count=prior.word_count,
            elapsed_seconds=0.0,
            started_at=now,
            completed_at=now,
            error="",
        )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _unique_scene_ids(scene_ids: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for scene_id in scene_ids:
        if scene_id not in seen:
            seen.add(scene_id)
            ordered.append(scene_id)
    return ordered


def _summarize_cost_log(path: Path) -> dict[str, Any]:
    """Aggregate ModelRouter cost_log.jsonl for run-level summaries."""
    summary: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "entry_count": 0,
        "malformed_entries": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
    }
    if not path.exists():
        return summary

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            summary["malformed_entries"] += 1
            continue
        input_tokens = _safe_int(entry.get("input_tokens"))
        output_tokens = _safe_int(entry.get("output_tokens"))
        total_tokens = _safe_int(entry.get("total_tokens")) or input_tokens + output_tokens
        summary["entry_count"] += 1
        summary["input_tokens"] += input_tokens
        summary["output_tokens"] += output_tokens
        summary["total_tokens"] += total_tokens
        summary["cost_usd"] += _safe_float(entry.get("cost_usd"))

    summary["cost_usd"] = round(float(summary["cost_usd"]), 8)
    return summary


def _safe_int(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
