# Phase 14 Eval Runbook

This is the first Phase 14 slice: local evals for one completed scene.

## Command

Run the latest completed scene under `data/**/scenes/`:

```bash
make eval
```

Run a specific scene:

```bash
make eval EVAL_ARGS="--scene data/phase7_smoke_test/without_dreaming/data/series/phase7-smoke-test-series/data/books/phase7-smoke-test-book-01/scenes/scene_01_smoke_test.md"
```

Override thresholds:

```bash
make eval EVAL_ARGS="--scene path/to/scene.md --voice-threshold 0.75 --ai-tell-threshold 0.50"
```

Equivalent environment variables:

```bash
VOICE_CONSISTENCY_THRESHOLD=0.75 AI_TELL_THRESHOLD=0.50 make eval
```

## Behavior

`scripts/run_eval.py` evaluates one scene with:

- `VoiceConsistencyMetric`: score range `0.0` to `1.0`, higher is better.
- `AITellMetric`: score range `0.0` to `1.0`, higher is cleaner.

The command prints each score, threshold, pass/fail status, and the metric reason. It exits `0` only when both metrics meet their thresholds. It exits `1` when either metric is below threshold. Missing scene input is a CLI usage error.

## Offline Default

The runner is deterministic by default and does not require real API calls. `VoiceConsistencyMetric` uses a deterministic fallback heuristic unless `--use-llm-voice` is passed or `FF_EVAL_USE_LLM=true` is set. `AITellMetric` is deterministic and uses the structural analyzer, with a local regex fallback if the analyzer is unavailable.

## JSON Output

Use `--json` for machine-readable output:

```bash
make eval EVAL_ARGS="--scene path/to/scene.md --json"
```

## Checkpoint Resume Status

SQLite checkpoint resume is implemented in `SceneStateMachine` and enabled by default for normal orchestrator `--job` runs. The CLI prints the stable `thread_id`; use that value with `--resume` if a run needs to continue from its checkpoint.

## Current Scope

This slice does not wire DeepEval into CI and does not perform production-tier model promotion. It provides the local metric runner, deterministic tests, and checkpoint resume foundation needed to continue Phase 14 hardening work.
