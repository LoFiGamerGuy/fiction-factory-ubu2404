# Phase 14 Model Promotion Results

Date: 2026-06-10

## Verdict

Production-tier acceptance passed the same 3-scene gate as test-tier. Keep `model_router.json` defaulted to `test`; use `scripts/run_phase14_acceptance.py --model-tier production` for deliberate production runs and comparisons.

## Commands Run

```bash
make phase14-acceptance PHASE14_ARGS="--model-tier test --provider openai --run-id test-tier-local --eval"
make phase14-acceptance PHASE14_ARGS="--model-tier production --provider anthropic --run-id production-tier-local --eval"
```

Standalone corpus eval was also run on both scene directories with `--require-scenes 3`.

## Comparison

| Run | Tier / provider | Runtime | GO scenes | Eval | Word total |
|---|---|---:|---:|---|---:|
| `test-tier-local` | `test` / `openai` | 61.795s | 3/3 | PASS | 1455 |
| `production-tier-local` | `production` / `anthropic` | 90.540s | 3/3 | PASS | 1627 |

## Eval Scores

| Run | Scene | VoiceConsistencyMetric | AITellMetric |
|---|---|---:|---:|
| `test-tier-local` | `scene_01_meet_cute` | 0.9000 | 0.8000 |
| `test-tier-local` | `scene_02_first_date` | 0.9500 | 0.9000 |
| `test-tier-local` | `scene_03_first_conflict` | 0.9000 | 0.8000 |
| `production-tier-local` | `scene_01_meet_cute` | 0.9500 | 0.9000 |
| `production-tier-local` | `scene_02_first_date` | 0.9400 | 0.8000 |
| `production-tier-local` | `scene_03_first_conflict` | 0.9500 | 0.9000 |

## Notes

- Both runs produced 3/3 `GO` convergence decisions with no force-resolved scenes.
- Both runs updated dashboard summaries and BookMetrics totals.
- WUPHF ran in graceful-degradation mode because local WUPHF credentials were not configured.
- Exact token/cost comparison is not available yet because `ModelRouter` currently writes zero token counts to the cost log. Runtime and eval scores are the reliable comparison dimensions for this run.
