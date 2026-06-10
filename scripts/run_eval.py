#!/usr/bin/env python3
"""Phase 14 eval runner for the latest or provided completed scene."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# ruff: noqa: E402
from deepeval.test_case import LLMTestCase

from tests.eval.ai_tell_metric import AITellMetric
from tests.eval.voice_consistency_metric import VoiceConsistencyMetric


@dataclass(frozen=True)
class MetricScore:
    """One metric score and pass/fail result."""

    name: str
    score: float
    threshold: float
    passed: bool
    reason: str


@dataclass(frozen=True)
class EvalRun:
    """Complete eval result for one scene."""

    scene_path: Path
    voice: MetricScore
    ai_tell: MetricScore

    @property
    def passed(self) -> bool:
        return self.voice.passed and self.ai_tell.passed


@dataclass(frozen=True)
class EvalSuite:
    """Complete eval result for a scene corpus."""

    runs: list[EvalRun]

    @property
    def passed(self) -> bool:
        return bool(self.runs) and all(run.passed for run in self.runs)

    @property
    def scene_count(self) -> int:
        return len(self.runs)


def _default_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{name} must be a float, got {raw!r}") from exc


def _threshold(value: str) -> float:
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("threshold must be between 0.0 and 1.0")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _find_latest_completed_scene(data_root: Path) -> Path | None:
    """Return the newest completed scene markdown/text/json file under data_root."""
    candidates = _collect_scene_paths(data_root, require_scenes_dir=True)

    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _collect_scene_paths(scene_root: Path, require_scenes_dir: bool = False) -> list[Path]:
    """Return stable scene files under a root, excluding drafts."""
    if not scene_root.exists():
        return []

    candidates: list[Path] = []
    for suffix in ("*.md", "*.txt", "*.json"):
        for path in scene_root.rglob(suffix):
            if "drafts" in path.parts:
                continue
            if require_scenes_dir and "scenes" not in path.parts:
                continue
            if path.is_file():
                candidates.append(path)

    return sorted(candidates, key=lambda path: str(path.relative_to(scene_root)))


def _read_scene_text(scene_path: Path) -> str:
    """Read scene prose from markdown/text, or extract likely prose fields from JSON."""
    raw = scene_path.read_text(encoding="utf-8")
    if scene_path.suffix.lower() != ".json":
        return raw.strip()

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()

    extracted = _extract_text(payload)
    return extracted.strip() if extracted else raw.strip()


def _extract_text(value: Any) -> str | None:
    preferred_keys = (
        "final_text",
        "scene_text",
        "revised_text",
        "draft_text",
        "draft",
        "text",
        "content",
        "actual_output",
    )
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in preferred_keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        for candidate in value.values():
            extracted = _extract_text(candidate)
            if extracted:
                return extracted
    if isinstance(value, list):
        for candidate in value:
            extracted = _extract_text(candidate)
            if extracted:
                return extracted
    return None


def evaluate_scene(
    scene_path: Path,
    voice_threshold: float,
    ai_tell_threshold: float,
    model_tier: str,
    use_llm_voice: bool,
    use_llm_ai_tell: bool,
) -> EvalRun:
    prose = _read_scene_text(scene_path)
    test_case = LLMTestCase(input=f"Evaluate scene: {scene_path.name}", actual_output=prose)

    voice_metric = VoiceConsistencyMetric(
        threshold=voice_threshold,
        model_tier=model_tier,
        use_llm_judge=use_llm_voice,
    )
    voice_score = voice_metric.measure(test_case)

    ai_tell_metric = AITellMetric(
        threshold=ai_tell_threshold,
        use_llm_judge=use_llm_ai_tell,
    )
    ai_tell_score = ai_tell_metric.measure(test_case)

    return EvalRun(
        scene_path=scene_path,
        voice=MetricScore(
            name=voice_metric.name,
            score=voice_score,
            threshold=voice_threshold,
            passed=voice_metric.is_successful(),
            reason=voice_metric.reason,
        ),
        ai_tell=MetricScore(
            name=ai_tell_metric.name,
            score=ai_tell_score,
            threshold=ai_tell_threshold,
            passed=ai_tell_metric.is_successful(),
            reason=ai_tell_metric.reason,
        ),
    )


def evaluate_scenes(
    scene_paths: list[Path],
    voice_threshold: float,
    ai_tell_threshold: float,
    model_tier: str,
    use_llm_voice: bool,
    use_llm_ai_tell: bool,
) -> EvalSuite:
    """Evaluate a corpus of scenes and return aggregate pass/fail status."""
    return EvalSuite(
        runs=[
            evaluate_scene(
                scene_path=scene_path,
                voice_threshold=voice_threshold,
                ai_tell_threshold=ai_tell_threshold,
                model_tier=model_tier,
                use_llm_voice=use_llm_voice,
                use_llm_ai_tell=use_llm_ai_tell,
            )
            for scene_path in scene_paths
        ]
    )


def _print_human(result: EvalRun) -> None:
    print("Phase 14 Eval")
    print(f"Scene: {result.scene_path}")
    for metric in (result.voice, result.ai_tell):
        status = "PASS" if metric.passed else "FAIL"
        print(f"{metric.name}: score={metric.score:.4f} threshold={metric.threshold:.4f} {status}")
        print(f"  reason: {metric.reason}")
    print(f"Result: {'PASS' if result.passed else 'FAIL'}")


def _print_suite_human(suite: EvalSuite) -> None:
    print("Phase 14 Eval Suite")
    print(f"Scenes: {suite.scene_count}")
    for run in suite.runs:
        status = "PASS" if run.passed else "FAIL"
        print(f"Scene: {run.scene_path} {status}")
        print(
            "  "
            f"VoiceConsistencyMetric={run.voice.score:.4f}/{run.voice.threshold:.4f} "
            f"AITellMetric={run.ai_tell.score:.4f}/{run.ai_tell.threshold:.4f}"
        )
    print(f"Result: {'PASS' if suite.passed else 'FAIL'}")


def _print_json(result: EvalRun) -> None:
    print(json.dumps(_run_payload(result), indent=2, sort_keys=True))


def _metric_payload(metric: MetricScore) -> dict[str, Any]:
    return {
        "name": metric.name,
        "score": metric.score,
        "threshold": metric.threshold,
        "passed": metric.passed,
        "reason": metric.reason,
    }


def _run_payload(result: EvalRun) -> dict[str, Any]:
    return {
        "scene_path": str(result.scene_path),
        "passed": result.passed,
        "metrics": {
            "voice_consistency": _metric_payload(result.voice),
            "ai_tell": _metric_payload(result.ai_tell),
        },
    }


def _print_suite_json(suite: EvalSuite) -> None:
    payload = {
        "passed": suite.passed,
        "scene_count": suite.scene_count,
        "scenes": [_run_payload(run) for run in suite.runs],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 14 eval metrics on scenes.")
    parser.add_argument(
        "--scene",
        type=Path,
        help="Scene file to evaluate. If omitted, the newest data/**/scenes/* file is used.",
    )
    parser.add_argument(
        "--scene-dir",
        type=Path,
        help="Evaluate every markdown/text/json scene under this directory.",
    )
    parser.add_argument(
        "--max-scenes",
        type=_positive_int,
        help="Limit --scene-dir evaluation to the first N scenes in stable path order.",
    )
    parser.add_argument(
        "--require-scenes",
        type=_positive_int,
        help="Fail unless at least this many scenes are available for evaluation.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=WORKSPACE_ROOT / "data",
        help="Root searched for latest completed scene when --scene is omitted.",
    )
    parser.add_argument(
        "--voice-threshold",
        type=_threshold,
        default=_default_float_env("VOICE_CONSISTENCY_THRESHOLD", 0.75),
        help="Minimum VoiceConsistencyMetric score. Env: VOICE_CONSISTENCY_THRESHOLD.",
    )
    parser.add_argument(
        "--ai-tell-threshold",
        type=_threshold,
        default=_default_float_env("AI_TELL_THRESHOLD", 0.50),
        help="Minimum AITellMetric score. Env: AI_TELL_THRESHOLD.",
    )
    parser.add_argument(
        "--model-tier",
        default=os.getenv("MODEL_TIER", "test"),
        choices=("test", "production"),
        help="Model tier used only when --use-llm-voice is set.",
    )
    parser.add_argument(
        "--use-llm-voice",
        action="store_true",
        help="Opt into Claude-as-judge for voice consistency; offline heuristic is default.",
    )
    parser.add_argument(
        "--use-llm-ai-tell",
        action="store_true",
        help="Reserve hook for critical AI-tell LLM judging; deterministic score remains primary.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.scene and args.scene_dir:
        parser.error("Pass either --scene or --scene-dir, not both.")

    if args.max_scenes and not args.scene_dir:
        parser.error("--max-scenes requires --scene-dir.")

    if args.scene_dir:
        scene_paths = _collect_scene_paths(args.scene_dir)
        if args.max_scenes:
            scene_paths = scene_paths[: args.max_scenes]
        if args.require_scenes and len(scene_paths) < args.require_scenes:
            parser.error(
                f"Found {len(scene_paths)} scene(s) under {args.scene_dir}; "
                f"required {args.require_scenes}."
            )
        if not scene_paths:
            parser.error(f"No scene files found under {args.scene_dir}.")

        suite = evaluate_scenes(
            scene_paths=[path.resolve() for path in scene_paths],
            voice_threshold=args.voice_threshold,
            ai_tell_threshold=args.ai_tell_threshold,
            model_tier=args.model_tier,
            use_llm_voice=args.use_llm_voice,
            use_llm_ai_tell=args.use_llm_ai_tell,
        )
        if args.json:
            _print_suite_json(suite)
        else:
            _print_suite_human(suite)
        return 0 if suite.passed else 1

    scene_path = args.scene
    if scene_path is None:
        scene_path = _find_latest_completed_scene(args.data_root)
        if scene_path is None:
            parser.error(
                f"No completed scene found under {args.data_root}. Pass --scene path/to/scene.md."
            )

    scene_path = scene_path.resolve()
    if not scene_path.exists():
        parser.error(f"Scene file does not exist: {scene_path}")

    result = evaluate_scene(
        scene_path=scene_path,
        voice_threshold=args.voice_threshold,
        ai_tell_threshold=args.ai_tell_threshold,
        model_tier=args.model_tier,
        use_llm_voice=args.use_llm_voice,
        use_llm_ai_tell=args.use_llm_ai_tell,
    )

    if args.json:
        _print_json(result)
    else:
        _print_human(result)

    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
