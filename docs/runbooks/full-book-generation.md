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

The command writes generated data under `data/book_acceptance/{run_id}/`, which is gitignored. Book acceptance defaults to `--acceptance-mode draft`: rich drafts may exceed the strict final word-count gate by up to `--draft-surplus-allowed-pct 0.25` when scenes, eval, dashboard checks, and force-resolution checks are clean. Acceptance runs also enable adaptive word-budget control by default: the fixture book target is redistributed across remaining scenes after each actual scene word count is known.

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
- `word_budget_status`, including the verifier book target, original planned scene-target total, actual words so far, remaining budget, projected final count, minimum scene target, and one row per scene with planned target, adjusted target, actual words, remaining scene count, and projection before/after the scene.
- `previous_failed_scene_ids` from prior status history and `checkpoint_thread_ids` for every scene in the current run.
- Manuscript path and summary path.
- Ledger dashboard summary.
- `cost_summary` with cost log path, entry count, input/output/total tokens, malformed entry count, and total USD cost.
- `files_api` with the opt-in Files API flag and run-local uploaded file IDs.
- Optional `eval_status`, strict `verifier_status`, and `draft_acceptance_status` blocks when those steps are wired or supplied.

The Author Dashboard exposes the same durable summary through `GET /books/{book_id}/summary`. The Word Budget card reads `word_budget_status` from that endpoint and shows the book target, planned scene-target total, actual words, remaining budget, projected final count, minimum scene target, latest adjusted scene target, and the per-scene controller trace.

## Author Dashboard Historical Views

The dashboard shell keeps the same local FastAPI + React workflow and adds historical cards over existing run artifacts:

- `PromiseLedger.tsx` reads `GET /books/{book_id}/promises`, which exposes the SQLite `PromiseLedger` grouped by `promise_id`.
- `IntimacyTimeline.tsx` reads `GET /books/{book_id}/intimacy`, which exposes `IntimacyEscalationLedger` events in append order.
- `SeriesTimeline.tsx` reads `GET /series/{series_id}/promises`. The endpoint reads legacy `series_promises.jsonl` when present and the runtime SQLite `SeriesPromiseLedger` at `data_root/series/{series_id}/series_promises.db`.
- `SkillLibrary.tsx` reads `GET /series/{series_id}/evoskill` for promoted EvoSkill markdown files under `data_root/{series_id}/skills/`.
- `VoiceCalibration.tsx` reads `GET /series/{series_id}/voice_calibration`, resolving a run-local `voice_profile.yaml` from `data_root/{series_id}/profiles/`, `data_root/series/{series_id}/profiles/`, or the sibling acceptance-run `series/{series_id}/profiles/` tree.

These cards are read-only author views. They do not mutate ledgers, do not trigger generation, and do not require production-tier model access.

## Dashboard Startup Against A Generated Run

The FastAPI dashboard backend reads local artifacts from `FF_DASHBOARD_DATA_ROOT`. The `make dashboard` target exposes that as `DASHBOARD_DATA_ROOT` and can prefill the React selectors with run/book/series IDs:

```bash
make dashboard \
  DASHBOARD_DATA_ROOT="data/book_acceptance/test-tier-novella-budgeted/data" \
  DASHBOARD_RUN_ID="test-tier-novella-budgeted_ch06_sc02_hea_resolution" \
  DASHBOARD_BOOK_ID="book-acceptance-romance-novella-01" \
  DASHBOARD_SERIES_ID="book-acceptance-series" \
  DASHBOARD_CHARACTER_IDS="emma,marcus"
```

Equivalent manual startup:

```bash
FF_DASHBOARD_DATA_ROOT="data/book_acceptance/test-tier-novella-budgeted/data" \
  .venv/bin/python -m uvicorn api.main:app --reload --port 8000
```

```bash
cd dashboard && \
  VITE_DEFAULT_RUN_ID="test-tier-novella-budgeted_ch06_sc02_hea_resolution" \
  VITE_DEFAULT_BOOK_ID="book-acceptance-romance-novella-01" \
  VITE_DEFAULT_SERIES_ID="book-acceptance-series" \
  VITE_DEFAULT_CHARACTER_IDS="emma,marcus" \
  npm run dev
```

Expected budgeted novella checks:

- `GET /books/book-acceptance-romance-novella-01/summary` resolves the sibling `series/book-acceptance-series/data/books/.../book_run_summary.json` and returns `summary_found = true` with `word_budget_status.enabled = true`.
- `GET /books/book-acceptance-romance-novella-01/metrics/history?granularity=scene&metric=word_count` returns 12 scene points.
- `GET /books/book-acceptance-romance-novella-01/quality_gates` returns 12 quality gate rows.
- `GET /series/book-acceptance-series/evoskill` returns promoted skills when the EvoSkill closure pass has been run against that data root.

If `summary_found = false`, first verify the generated acceptance run directory exists locally. The `data/book_acceptance/` tree is gitignored and may not exist in a fresh checkout.

Dogfood result, 2026-06-12:

- Data root: `data/book_acceptance/test-tier-novella-budgeted/data`.
- Run status: `test-tier-novella-budgeted_ch06_sc02_hea_resolution` completed with routing decision `GO`.
- Summary: `acceptance_passed = true`, adaptive `word_budget_status.enabled = true`, draft actual word count `4403`.
- Ledgers: `word_count_total = 4403`.
- Metric history: 12 scene rows and 6 chapter rows for `word_count`.
- Quality gates: 12 rows.
- EvoSkill: three local nightly passes promoted 3 skills for `book-acceptance-series`, making the dashboard Skill Library card non-empty for this run.

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

## Adaptive Word-Budget Control

Acceptance runs pass the fixture verifier target into `BookRunner.run_book(word_budget_target=...)`. Before each scene, `WordBudgetController` computes:

- The planned target for the current scene.
- Actual finalized words so far.
- Remaining scenes and remaining book budget.
- Projected final word count based on the current actual-to-adjusted ratio.
- The adjusted target sent to `JobContext.word_count_target` and therefore to `WriterAgent`.

The adjusted target is proportional to the remaining book budget and the remaining planned scene weights. It is capped at the original scene target so under-budget scenes do not cause runaway expansion, and it is floored at 250 words so later scenes are compressed but not made useless. This is a prompt-budget control loop only; it does not change `BookStructuralVerifier`, `draft_acceptance_status`, or `--acceptance-mode final`.

For the novella fixture, the controller starts from the 4,600-word verifier target rather than the twelve fixed 450-word scene prompts. That means the first scene target is about 383 words, then later targets adapt if actual production-tier output runs long.

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

## First Production Scaffold

The first full-length production-ready scaffold lives at:

- Series root: `data/series/cedar-harbor-romance/`
- Series spec: `data/series/cedar-harbor-romance/spec.yaml`
- Book spec: `data/series/cedar-harbor-romance/data/books/book01/spec.yaml`
- Run config: `data/series/cedar-harbor-romance/pipeline_config.json`
- Generated scene inventory: `data/series/cedar-harbor-romance/data/books/book01/scene_inventory.json`

The scaffold is `book01`, titled `The Renovation Pact`: a 65,000-word contemporary small-town romance planned as 25 chapters x 2 scenes. The book spec includes 50 authored scene briefs. `BookStructurePlanner` carries these briefs into `scene_inventory.json`, and the orchestrator now uses `SceneSlot.scene_brief` for scene jobs.

Validate the scaffold:

```bash
.venv/bin/python -m pipeline.orchestrator \
  --validate-spec data/series/cedar-harbor-romance/spec.yaml \
  --config data/series/cedar-harbor-romance/pipeline_config.json
```

Regenerate the deterministic scene inventory:

```bash
.venv/bin/python -m pipeline.orchestrator \
  --init-book cedar-harbor-romance 1 \
  --config data/series/cedar-harbor-romance/pipeline_config.json
```

Run the first scene through the normal scene loop, when live test-tier model spend is intentional:

```bash
.venv/bin/python -m pipeline.orchestrator \
  --job ch01_sc01 \
  --config data/series/cedar-harbor-romance/pipeline_config.json
```

Continue scenes in `scene_inventory.json` order. Keep `model_router.json` defaulted to `test`; switch to production tier only through explicit run-local config changes after test-tier proof.

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
- `/books/book-acceptance-romance-novella-01/summary`: `word_budget_status.enabled = true`.
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
- `/books/book-acceptance-romance-novella-01/summary`: resolves `book_run_summary.json` from the sibling `series/` output tree.
- `/books/book-acceptance-romance-novella-01/ledgers`: `word_count_total = 5464`.
- `/books/book-acceptance-romance-novella-01/metrics/history?granularity=scene&metric=word_count`: 12 rows.
- `/books/book-acceptance-romance-novella-01/metrics/history?granularity=chapter&metric=word_count`: 6 rows.
- `/books/book-acceptance-romance-novella-01/quality_gates`: 12 rows.

Qualitative sample, `ch02_sc02_first_spark`:

- Test tier used a serviceable but generic romantic beat: ladder proximity, shoulder brush, direct boundary dialogue, and explicit spark language.
- Production tier used more concrete business/plumbing details and quieter subtext: the drip starts at a precise time, the repair action is specific, and the romantic tension is carried through shared physical problem-solving rather than named emotion.

Conclusion:

Production-tier novella generation is operational and stronger on deterministic eval averages. It is acceptable as a rich draft because the overage is within the +25% draft surplus ceiling, but it is not publish-ready because it exceeded the strict structural word-count gate. New acceptance runs include adaptive word-budget control to reduce this overrun risk, but keep `model_router.json` defaulted to `test`; run production tier only through explicit run-local commands when live API spend is intentional.

## Budgeted Novella Acceptance Results

Date: 2026-06-11

Test-tier command:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--fixture novella --model-tier test --provider openai --run-id test-tier-novella-budgeted --force"
```

Production-tier command, run with explicit user approval:

```bash
make book-acceptance BOOK_ACCEPTANCE_ARGS="--fixture novella --model-tier production --provider anthropic --run-id production-tier-novella-budgeted --force"
```

Result: PASS for both runs. The production-tier budgeted run passed strict `BookStructuralVerifier`, which the earlier unbudgeted production-tier run failed.

| Metric | Budgeted test tier | Prior production tier | Budgeted production tier |
|---|---:|---:|---:|
| Provider | OpenAI | Anthropic | Anthropic |
| Scenes completed | 12/12 | 12/12 | 12/12 |
| GO decisions | 12/12 | 12/12 | 12/12 |
| Force-resolved scenes | 0 | 0 | 0 |
| Planned scene-target total | 5400 | 5400 | 5400 |
| Controller book target | 4600 | n/a | 4600 |
| Manuscript word count | 4403 | 5464 | 4614 |
| Draft acceptance | PASS: `draft_within_target` | PASS: `draft_surplus` (+18.78%) | PASS: `draft_surplus` (+0.30%) |
| BookStructuralVerifier | PASS | FAIL: word count outside [4140-5060] | PASS |
| Corpus eval | PASS, 12 scenes | PASS, 12 scenes | PASS, 12 scenes |
| VoiceConsistencyMetric average | 0.9254 | 0.9458 | 0.9517 |
| AITellMetric average | 0.8250 | 0.8583 | 0.9167 |
| Runtime | 189.835s | 304.54s | 243.363s |
| Cost log entries | 23 | 24 | 20 |
| Total tokens | 22482 | 45143 | 33579 |
| Estimated cost | $0.00872145 | $0.331653 | $0.240705 |

Artifacts:

- Budgeted test summary: `data/book_acceptance/test-tier-novella-budgeted/series/book-acceptance-series/data/books/book-acceptance-romance-novella-01/book_run_summary.json`
- Budgeted production summary: `data/book_acceptance/production-tier-novella-budgeted/series/book-acceptance-series/data/books/book-acceptance-romance-novella-01/book_run_summary.json`
- Budgeted production manuscript: `data/book_acceptance/production-tier-novella-budgeted/series/book-acceptance-series/data/books/book-acceptance-romance-novella-01/manuscript.md`

Controller trace notes:

- The fixed fixture scene prompts still plan 12 x 450 words = 5400 words.
- `WordBudgetController` uses the 4600-word verifier target for acceptance runs.
- The budgeted production run sent adjusted scene targets between 383 and 403 words and finished at 4614 words.
- The production run reduced the prior overage by 850 words, moved from strict verifier FAIL to PASS, reduced total tokens by 11564, and reduced estimated cost by about $0.09.
