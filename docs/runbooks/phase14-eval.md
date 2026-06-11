# Phase 14 Eval Runbook

This is the local Phase 14 eval path: deterministic evals for one completed scene or a scene corpus.

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

Run a 3-scene local acceptance corpus:

```bash
make eval EVAL_ARGS="--scene-dir path/to/scenes --require-scenes 3"
```

Limit corpus size in stable path order:

```bash
make eval EVAL_ARGS="--scene-dir path/to/scenes --max-scenes 3 --require-scenes 3"
```

Run the full local 3-scene Phase 14 acceptance path with test-tier models:

```bash
make phase14-acceptance PHASE14_ARGS="--model-tier test --provider openai"
```

Run the same acceptance path without corpus eval, useful while debugging generation only:

```bash
make phase14-acceptance PHASE14_ARGS="--model-tier test --provider openai --no-eval"
```

Production-tier comparison uses the same runner, but should only be run after the test-tier run passes and live API spend is intentional:

```bash
make phase14-acceptance PHASE14_ARGS="--model-tier production --provider anthropic"
```

Latest test-tier vs production-tier results are recorded in `docs/runbooks/phase14-model-promotion.md`.

Equivalent environment variables:

```bash
VOICE_CONSISTENCY_THRESHOLD=0.75 AI_TELL_THRESHOLD=0.50 make eval
```

## Behavior

`scripts/run_eval.py` evaluates one scene or all scene files under `--scene-dir` with:

- `VoiceConsistencyMetric`: score range `0.0` to `1.0`, higher is better.
- `AITellMetric`: score range `0.0` to `1.0`, higher is cleaner.

For single-scene mode, the command prints each score, threshold, pass/fail status, and metric reason. For corpus mode, it prints one line per scene plus aggregate pass/fail. It exits `0` only when every evaluated scene meets both thresholds. It exits `1` when any metric is below threshold. Missing scene input or too few scenes for `--require-scenes` is a CLI usage error.

`scripts/run_phase14_acceptance.py` runs three fixture Romance Module scenes through the full `JobRunner` path and writes a summary to `data/phase14_acceptance/{run_id}/phase14_acceptance_summary.json`. It writes a run-local `model_router.run.json` so `--model-tier production` does not mutate the repository's default `model_router.json`.

## Offline Default

The runner is deterministic by default and does not require real API calls. `VoiceConsistencyMetric` uses a deterministic fallback heuristic unless `--use-llm-voice` is passed or `FF_EVAL_USE_LLM=true` is set. `AITellMetric` is deterministic and uses the structural analyzer, with a local regex fallback if the analyzer is unavailable.

## JSON Output

Use `--json` for machine-readable output in either single-scene or corpus mode:

```bash
make eval EVAL_ARGS="--scene path/to/scene.md --json"
```

## Checkpoint Resume Status

SQLite checkpoint resume is implemented in `SceneStateMachine` and enabled by default for normal orchestrator `--job` runs. The CLI prints the stable `thread_id`; use that value with `--resume` if a run needs to continue from its checkpoint.

## Current Scope

This slice does not wire DeepEval into CI and does not itself approve production-tier model promotion. It provides the local metric runner, deterministic tests, 3-scene corpus gate, full 3-scene acceptance runner, and checkpoint resume foundation needed to complete Phase 14 hardening work.
