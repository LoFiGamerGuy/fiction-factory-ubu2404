# Cedar Harbor No-Live Hardening Report

Date: 2026-06-17

Scope: no-live follow-up after the full Anthropic Cedar Harbor test-tier pass. No model calls were made.

## Problem

The full-book manuscript summary had a reliable final count of `64982` words, but the embedded ledger dashboard summary could report stale accumulated state from prior proof runs. Root cause: `scripts/run_full_book.py` used the shared configured ledger root for mutable run ledgers across multiple proof run IDs.

## Fix

- Full-book ledgers now live under `data/books/{book_id}/runs/{run_id}/ledgers`.
- `book_run_summary.json` records `configured_data_root` and `ledger_data_root`.
- Resuming the same run ID reuses the same ledger root.
- Starting a different run ID gets an isolated ledger root.
- `--force` removes that run ID's ledger root before regeneration.
- Dashboard book-level endpoints prefer `book_run_summary.ledger_data_root` when present.

## Verification

Targeted tests:

```bash
./.venv/bin/pytest tests/unit/test_full_book_runner.py tests/unit/api/test_dashboard_api.py
```

Result: `30 passed`.

Full no-live gate:

```bash
make lint
OPENAI_API_KEY= ANTHROPIC_API_KEY= make test
```

Result: lint passed; tests passed with `400 passed, 6 skipped`.

Covered behavior:

- Run-local ledger roots differ across run IDs.
- Staged resume accumulates only new scenes without double-counting skipped scenes.
- `--force` resets the run-local ledger root.
- Dashboard `/books/{book_id}/ledgers` and `/metrics/history` follow `book_run_summary.ledger_data_root`.
- Old summaries without `ledger_data_root` remain readable.

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
