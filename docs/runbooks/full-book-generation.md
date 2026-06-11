# Full-Book Generation Runbook

This is the repeatable book-generation acceptance path that moves beyond Phase 14 scene acceptance toward full-book generation.

## Command

Run the eight-scene Romance Module fixture through the same `JobRunner` path used by Phase 14:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--model-tier test --provider openai"
```

Run the longer 12-scene novella fixture with:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--fixture novella --model-tier test --provider openai"
```

The command writes generated data under `data/book_acceptance/{run_id}/`, which is gitignored. Book acceptance defaults to `--acceptance-mode draft`: rich drafts may exceed the strict final word-count gate by up to `--draft-surplus-allowed-pct 0.25` when scenes, eval, dashboard checks, and force-resolution checks are clean.

By default, the command also runs deterministic corpus eval and BookStructuralVerifier after scene generation or resume. Draft acceptance requires deterministic corpus eval to pass. Disable eval only while debugging generation:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--run-id my-short-book --no-eval"
```

Resume is enabled by default. Re-running the same `--run-id` skips scenes whose latest status is completed and whose final scene file still exists:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--run-id my-short-book --model-tier test --provider openai"
```

Regenerate every scene intentionally with `--force`:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--run-id my-short-book --force --model-tier test --provider openai"
```

Run strict final-manuscript acceptance instead of draft acceptance with:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--fixture novella --acceptance-mode final --model-tier test --provider openai"
```

## Outputs

- `book_run_summary.json` under the generated book directory.
- `model_router.run.json` at the run root, so `model_router.json` remains defaulted to `test`.
- `cost_log.jsonl` at the run root with per-call token and cost metadata.
- Per-scene final files under `series/book-acceptance-series/data/books/book-acceptance-romance-01/scenes/`.
- Per-scene status records in `book_run_status.jsonl` under the book directory.
- Ordered manuscript output at `manuscript.md` under the book directory.
- Optional Claude Files API IDs under `data/{series_id}/file_ids.json` inside the generated run root.

## Status Records

`pipeline.book_runner.BookRunner` appends one JSONL record per attempted scene with:

- `scene_id`, `chapter_id`, `job_id`, and `thread_id`.
- `status`, `output_path`, `convergence_decision`, `revise_count`, and `force_resolved`.
- `word_count`, elapsed time, timestamps, and error text.

Skipped scenes are recorded as `status = "skipped"` with the prior checkpoint `thread_id`, convergence decision, force-resolved flag, and word count. Failed historical records remain in the JSONL file unless a run is forced.

## Manuscript Format

`BookRunner.assemble_manuscript()` reads finalized scene files in the supplied fixture or `SceneInventory` order. Missing finalized scene files fail with a `FileNotFoundError` naming the missing scene and path.

The deterministic manuscript format is:

```markdown
# {book_id}

## Chapter {chapter_id}

### Scene {scene_id}

{scene text}
```

## Book Summary

`book_run_summary.json` records the durable run contract:

- Run ID, book ID, series ID, model tier, provider, and scene directory.
- Per-scene statuses from `book_run_status.jsonl`.
- Total word count, GO count, force-resolved count, failed scene IDs, and elapsed time.
- `acceptance_mode` and top-level `acceptance_passed`, where `draft` mode uses `draft_acceptance_status` and `final` mode uses strict verifier acceptance.
- `previous_failed_scene_ids` from prior status history and `checkpoint_thread_ids` for every scene in the current run.
- Manuscript path and summary path.
- Ledger dashboard summary.
- `cost_summary` with cost log path, entry count, input/output/total tokens, malformed entry count, and total USD cost.
- `files_api` with the opt-in Files API flag and run-local uploaded file IDs.
- Optional `eval_status`, strict `verifier_status`, and `draft_acceptance_status` blocks when those steps are wired or supplied.

## Acceptance Modes

`--acceptance-mode draft` is the default for book acceptance runs. It answers: did the system generate a complete, evaluable draft that is safe to take into editing? It does not loosen `BookStructuralVerifier`; it records that verifier result separately.

Draft acceptance passes when:

- All planned scenes complete.
- No scenes fail.
- No scenes are force-resolved.
- Deterministic corpus eval passes.
- Dashboard API checks pass if they were run.
- `actual_word_count <= target_word_count * (1 + draft_surplus_allowed_pct)`.

`draft_acceptance_status` records `target_word_count`, `actual_word_count`, `surplus_words`, `surplus_pct`, `draft_surplus_allowed_pct`, and `within_draft_surplus`. A passing over-target draft is classified as `draft_surplus`.

`--acceptance-mode final` preserves the prior strict behavior: top-level `acceptance_passed` requires the normal scene/run checks and a passing `BookStructuralVerifier`. Use final mode for publish-ready manuscript gating.

## Token And Cost Accounting

`ModelRouter` writes one `cost_log.jsonl` entry for every provider call. Entries include `input_tokens`, `output_tokens`, `total_tokens`, `cost_usd`, provider, model, job ID, agent ID, duration, and timestamp.

OpenAI usage is read from `prompt_tokens` and `completion_tokens`. Anthropic usage is read from `input_tokens` and `output_tokens`; cache creation/read input tokens are counted as input tokens. Missing usage fields fall back to zero so local providers and older SDK paths do not break scene execution.

`BookRunner.write_book_run_summary()` aggregates the selected cost log into `book_run_summary.json` as `cost_summary`. The short-book acceptance runner passes the run-local `cost_log.jsonl` path.

## Files API Hook

Files API upload is opt-in for the short-book runner:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--model-tier test --provider anthropic --upload-files"
```

The hook creates run-local fixture assets for the series bible, voice profile, and character sheets, uploads them through `FilesAPIClient`, registers returned file IDs in `ManagedAgentConfig`, and writes IDs to `data/{series_id}/file_ids.json` under the generated run root. File IDs are provider metadata, not secrets, but they are still kept out of source files.

## Production-Tier Rule

Keep `model_router.json` defaulted to `test`. Production comparison is explicit only:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--model-tier production --provider anthropic"
```

Run production-tier only when live API spend is intentional.

## Live Acceptance Results

Date: 2026-06-10

Command:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--model-tier test --provider openai --run-id test-tier-short-book-local"
```

Result: PASS.

| Metric | Result |
|---|---:|
| Scenes completed | 8/8 |
| GO decisions | 8/8 |
| Force-resolved scenes | 0 |
| Manuscript word count | 3075 |
| Corpus eval | PASS, 8 scenes |
| BookStructuralVerifier | PASS |
| VoiceConsistencyMetric range | 0.9000-0.9500 |
| AITellMetric range | 0.8000-1.0000 |

Artifacts:

- Summary: `data/book_acceptance/test-tier-short-book-local/series/book-acceptance-series/data/books/book-acceptance-romance-01/book_run_summary.json`
- Manuscript: `data/book_acceptance/test-tier-short-book-local/series/book-acceptance-series/data/books/book-acceptance-romance-01/manuscript.md`
- Scene directory: `data/book_acceptance/test-tier-short-book-local/series/book-acceptance-series/data/books/book-acceptance-romance-01/scenes/`
- Quality gates: `data/book_acceptance/test-tier-short-book-local/data/book-acceptance-romance-01/quality_gate_history.jsonl`
- EvoSkill traces: `data/book_acceptance/test-tier-short-book-local/data/book-acceptance-series/traces/`

Notes:

- WUPHF ran in graceful-degradation mode because local WUPHF credentials were not configured.
- This run predated real token extraction. New runs include nonzero token counts when provider usage metadata is available.
- Several scenes produced `warn` quality tier but still routed GO; those are correctly classified as EvoSkill failure traces for learning.

## Live Novella Acceptance Results

Date: 2026-06-11

Command:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--fixture novella --model-tier test --provider openai --run-id test-tier-novella-local --force"
```

Result: PASS.

| Metric | Result |
|---|---:|
| Scenes completed | 12/12 |
| GO decisions | 12/12 |
| Force-resolved scenes | 0 |
| Manuscript word count | 4702 |
| Corpus eval | PASS, 12 scenes |
| BookStructuralVerifier | PASS |
| VoiceConsistencyMetric range | 0.8950-0.9600 |
| AITellMetric range | 0.5000-1.0000 |
| Cost log entries | 23 |
| Total tokens | 23545 |
| Estimated cost | $0.0092049 |

Artifact checks:

- Summary: `data/book_acceptance/test-tier-novella-local/series/book-acceptance-series/data/books/book-acceptance-romance-novella-01/book_run_summary.json`
- Manuscript: `data/book_acceptance/test-tier-novella-local/series/book-acceptance-series/data/books/book-acceptance-romance-novella-01/manuscript.md`
- Scene directory: `data/book_acceptance/test-tier-novella-local/series/book-acceptance-series/data/books/book-acceptance-romance-novella-01/scenes/`
- Quality gates: `data/book_acceptance/test-tier-novella-local/data/book-acceptance-romance-novella-01/quality_gate_history.jsonl`
- EvoSkill traces: `data/book_acceptance/test-tier-novella-local/data/book-acceptance-series/traces/`

Dashboard API checks against `data/book_acceptance/test-tier-novella-local/data`:

- `/runs/test-tier-novella-local_ch06_sc02_hea_resolution/status`: completed, GO.
- `/books/book-acceptance-romance-novella-01/ledgers`: `word_count_total = 4702`.
- `/books/book-acceptance-romance-novella-01/metrics/history?granularity=scene&metric=word_count`: 12 rows.
- `/books/book-acceptance-romance-novella-01/metrics/history?granularity=chapter&metric=word_count`: 6 rows.
- `/books/book-acceptance-romance-novella-01/quality_gates`: 12 rows.

Notes:

- WUPHF ran in graceful-degradation mode because local WUPHF credentials were not configured.
- Files API upload was not enabled for this run; `files_api.enabled = false`.
- All 12 scenes produced EvoSkill failure traces because quality tier was `warn` even though routing decision was GO.

EvoSkill closure after this run:

- Three local nightly passes processed the 12 novella traces.
- All 12 traces were classified as `failure/quality_gate_fail` with GO routing.
- Three accepted skills were promoted locally under `data/book_acceptance/test-tier-novella-local/data/book-acceptance-series/skills/`.
- The same three skills were promoted to the run-local WUPHF wiki mirror under `data/book_acceptance/test-tier-novella-local/wuphf_wiki/series-bible/book-acceptance-series/editorial-guidelines/`.

## Production-Tier Novella Comparison

Date: 2026-06-11

Command:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--fixture novella --model-tier production --provider anthropic --run-id production-tier-novella-local --force"
```

Result under the original strict-only runner: generation completed, deterministic eval passed, dashboard checks passed, overall acceptance failed on structural word count. Under the current default draft policy, the same word-count data is classified as `draft_surplus` and draft acceptance passes; strict final verification still fails.

| Metric | Test tier novella | Production tier novella |
|---|---:|---:|
| Provider | OpenAI | Anthropic |
| Model tier | `test` | `production` |
| Scenes completed | 12/12 | 12/12 |
| GO decisions | 12/12 | 12/12 |
| Force-resolved scenes | 0 | 0 |
| Manuscript word count | 4702 | 5464 |
| Draft acceptance | PASS: `draft_surplus` (+2.22%) | PASS: `draft_surplus` (+18.78%) |
| BookStructuralVerifier | PASS | FAIL: word count outside [4140-5060] |
| Corpus eval | PASS, 12 scenes | PASS, 12 scenes |
| VoiceConsistencyMetric average | 0.9258 | 0.9458 |
| AITellMetric average | 0.8167 | 0.8583 |
| Runtime | 189.463s | 304.54s |
| Cost log entries | 23 | 24 |
| Total tokens | 23545 | 45143 |
| Estimated cost | $0.0092049 | $0.331653 |

Artifacts:

- Test summary: `data/book_acceptance/test-tier-novella-local/series/book-acceptance-series/data/books/book-acceptance-romance-novella-01/book_run_summary.json`
- Production summary: `data/book_acceptance/production-tier-novella-local/series/book-acceptance-series/data/books/book-acceptance-romance-novella-01/book_run_summary.json`
- Production manuscript: `data/book_acceptance/production-tier-novella-local/series/book-acceptance-series/data/books/book-acceptance-romance-novella-01/manuscript.md`
- Production scene directory: `data/book_acceptance/production-tier-novella-local/series/book-acceptance-series/data/books/book-acceptance-romance-novella-01/scenes/`

Dashboard API checks against `data/book_acceptance/production-tier-novella-local/data`:

- `/runs/production-tier-novella-local_ch06_sc02_hea_resolution/status`: completed, GO.
- `/books/book-acceptance-romance-novella-01/ledgers`: `word_count_total = 5464`.
- `/books/book-acceptance-romance-novella-01/metrics/history?granularity=scene&metric=word_count`: 12 rows.
- `/books/book-acceptance-romance-novella-01/metrics/history?granularity=chapter&metric=word_count`: 6 rows.
- `/books/book-acceptance-romance-novella-01/quality_gates`: 12 rows.

Qualitative sample, `ch02_sc02_first_spark`:

- Test tier used a serviceable but generic romantic beat: ladder proximity, shoulder brush, direct boundary dialogue, and explicit spark language.
- Production tier used more concrete business/plumbing details and quieter subtext: the drip starts at a precise time, the repair action is specific, and the romantic tension is carried through shared physical problem-solving rather than named emotion.

Conclusion:

Production-tier novella generation is operational and stronger on deterministic eval averages. It is acceptable as a rich draft because the overage is within the +25% draft surplus ceiling, but it is not publish-ready because it exceeded the strict structural word-count gate. Keep `model_router.json` defaulted to `test`; run production tier only through explicit run-local commands until word-budget control is tightened.
