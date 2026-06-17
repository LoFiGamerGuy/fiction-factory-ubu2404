# Cedar Harbor No-Live Hardening Report

Date: 2026-06-17

Scope: no-live follow-up after the full Anthropic Cedar Harbor test-tier pass. No model calls were made.

## Problem 1 — Run-Shared Ledger State

The full-book manuscript summary had a reliable final count of `64982` words, but the embedded ledger dashboard summary could report stale accumulated state from prior proof runs. Root cause: `scripts/run_full_book.py` used the shared configured ledger root for mutable run ledgers across multiple proof run IDs.

## Fix 1 — Run-Local Ledgers

- Full-book ledgers now live under `data/books/{book_id}/runs/{run_id}/ledgers`.
- `book_run_summary.json` records `configured_data_root` and `ledger_data_root`.
- Resuming the same run ID reuses the same ledger root.
- Starting a different run ID gets an isolated ledger root.
- `--force` removes that run ID's ledger root before regeneration.
- Dashboard book-level endpoints prefer `book_run_summary.ledger_data_root` when present.

## Problem 2 — Placeholder Runtime Prose Metrics

The second no-live autopsy found that the old runtime `BookMetricsLedger` path still wrote placeholder prose-shape values for finalized scenes: fixed `interiority_pct = 0.20`, fixed `dialogue_ratio = 0.30`, fixed `scene_type = action`, and `ai_tell_count` based only on NoFly violations. Offline eval and structural analysis had real scene-specific signals, but the dashboard/context-pack/trace path was underreporting them.

Autopsy snapshot over the existing Cedar Harbor artifact:

- Durable manuscript summary: `64982` words.
- Historical embedded dashboard total: `146285` words from stale shared ledgers.
- Deterministic eval: PASS, `avg_voice_consistency = 0.9354`, `avg_ai_tell = 0.7722`, `min_ai_tell = 0.5575`.
- Text-metric helper averages: `dialogue_ratio = 0.3579`, `interiority_pct = 0.1706`, `exposition_pct = 0.1084`, `action_pct = 0.3497`, `sensory_density_per_1k = 14.30`, `sentence_length_avg = 13.58`.
- Structural-analysis averages: `avg_structural_weight = 3.00`, `max_structural_weight = 9`, `avg_structural_count = 2.98`.

## Fix 2 — Deterministic Runtime Metrics And Trace Enrichment

- `QualityAgent` now computes lightweight deterministic text metrics from edited scene text for runtime ledger writes and `QualityResult.metrics`.
- `BookMetricsEvent` now records computed word count, interiority, dialogue ratio, exposition, action, sensory density, em-dash density, sentence length, and `ai_tell_count = nofly_violations + structural_flags`.
- `QualityResult` carries `structural_weighted_score` and the computed metric map.
- `JobRunner` enriches EvoSkill traces with tier flags, NoFly count, structural flag count, weighted structural points, and numeric `metric_*` values.
- Metric extraction falls back to `JobContext.final_text` if `edited_text` is absent.

## Verification

Run-local ledger targeted tests:

```bash
./.venv/bin/pytest tests/unit/test_full_book_runner.py tests/unit/api/test_dashboard_api.py
```

Result: `30 passed`.

Metric and trace targeted tests:

```bash
./.venv/bin/pytest tests/unit/test_word_count_enforcement.py tests/unit/test_job_runner_phase9.py tests/integration/test_evoskill.py
```

Result: `27 passed`.

Full no-live gate:

```bash
make lint
OPENAI_API_KEY= ANTHROPIC_API_KEY= make test
```

Result: lint passed; tests passed with `402 passed, 6 skipped`.

Covered behavior:

- Run-local ledger roots differ across run IDs.
- Staged resume accumulates only new scenes without double-counting skipped scenes.
- `--force` resets the run-local ledger root.
- Dashboard `/books/{book_id}/ledgers` and `/metrics/history` follow `book_run_summary.ledger_data_root`.
- Old summaries without `ledger_data_root` remain readable.
- `QualityAgent` ledger writes use deterministic scene-specific metrics rather than constants.
- EvoSkill traces include numeric quality and text-shape fields that the nightly pass can inspect.

Dashboard dogfood against the existing Cedar Harbor artifact:

- `summary_found = true`
- `run_passed = true`
- `total_word_count = 64982`
- `summary_has_ledger_data_root = false`

The existing summary predates this patch, so it cannot retroactively provide run-local ledger state. New full-book summaries will.

EvoSkill dogfood:

```bash
OPENAI_API_KEY= ANTHROPIC_API_KEY= ./.venv/bin/python scripts/evoskill_nightly.py --data-root "data/series/cedar-harbor-romance/data/ledgers"
```

Result: `29` Cedar Harbor failure traces found, `1` local skill promoted.

Promoted skill path:

`data/series/cedar-harbor-romance/data/ledgers/cedar-harbor-romance/skills/aff9e356-e5b3-4497-bf1c-45cef3389750.md`

## Notes

- No generated manuscript prose is committed by this report.
- `model_router.json` remains defaulted to `test`.
- OpenAI live generation remains blocked by `429 insufficient_quota` and was not retried.
