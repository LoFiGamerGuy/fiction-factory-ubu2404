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

## Production Full-Book Runner

Use `make run-full-book` for committed production scaffolds. This is the unattended runner: it validates the series spec, loads or generates `scene_inventory.json`, builds a run-local `model_router.run.json`, runs scenes through `BookRunner.run_inventory()` in inventory order, assembles `manuscript.md`, writes `book_run_summary.json`, and then runs local eval/verifier/dashboard checks when applicable.

Safe first proof for the Cedar Harbor scaffold:

```bash
make run-full-book RUN_BOOK_ARGS="\
  --config data/series/cedar-harbor-romance/pipeline_config.json \
  --series-id cedar-harbor-romance \
  --book-id book01 \
  --run-id cedar-harbor-book01-test \
  --model-tier test \
  --provider openai \
  --max-scenes 3"
```

Use `--max-scenes 1` or `--max-scenes 3` for the first live proof. Do not run the full 50-scene book, or production tier, unless model spend has been explicitly approved.

Runner controls:

- `--resume` is enabled by default and skips completed scenes for the same run ID when the final scene file still exists.
- `--force` intentionally reruns all selected scenes and resets that run ID's status JSONL and run-local ledger root.
- `--stop-on-error` is the default; `--continue-on-error` attempts later scenes after a failure.
- `--no-eval` skips deterministic corpus eval for debugging.
- `--no-dashboard-checks` skips the local FastAPI summary-resolution check.

Partial `--max-scenes` runs truncate only the in-memory inventory. The source `scene_inventory.json` remains untouched, summary metadata records `inventory_total_scene_count`, and strict `BookStructuralVerifier` is marked skipped with `reason = "partial_run"`. Eval and dashboard checks still run against the partial artifact set when enabled; eval is scoped to the selected inventory scene paths, not every stale `*.md` file in the shared book scene directory.

Generation-time word-count enforcement happens before final verification: `QualityAgent` marks a scene `needs_review` when the edited text is below 90% of `JobContext.word_count_target`. That note routes through the normal REVISE loop, and `WriterAgent` receives the prior draft plus `word_count_under_target` feedback so it can expand rather than start blind. `WriterAgent` always recomputes `WriterOutput.word_count` from `draft_text`; model-reported word counts are never trusted. If retries are exhausted and a scene force-resolves, `make run-full-book` reports the unattended run as failed even when files were produced.

Runtime prose metrics are deterministic. `QualityAgent` computes `BookMetricsLedger` values from edited scene text instead of placeholders: word count, interiority, dialogue ratio, exposition, action, sensory density per 1K, em-dash density, sentence-length average, and `ai_tell_count = nofly_violations + structural_flags`. The same metrics are included in `QualityResult.metrics` and propagated into EvoSkill traces as numeric `metric_*` fields, alongside tier flags and weighted structural points.

Production runner outputs for `cedar-harbor-romance/book01`:

- `data/series/cedar-harbor-romance/data/books/book01/runs/{run_id}/book_run_status.jsonl`
- `data/series/cedar-harbor-romance/data/books/book01/runs/{run_id}/model_router.run.json`
- `data/series/cedar-harbor-romance/data/books/book01/runs/{run_id}/cost_log.jsonl`
- `data/series/cedar-harbor-romance/data/books/book01/runs/{run_id}/ledgers/`
- `data/series/cedar-harbor-romance/data/books/book01/scenes/*.md`
- `data/series/cedar-harbor-romance/data/books/book01/manuscript.md`
- `data/series/cedar-harbor-romance/data/books/book01/book_run_summary.json`

Generated production artifacts under the committed `data/series/*/data/books/*` tree are gitignored. Specs, profiles, bible seed files, character sheets, and `scene_inventory.json` remain trackable.

Production full-book ledgers are run-local. `scripts/run_full_book.py` writes `LedgerManager` state under `runs/{run_id}/ledgers/` and records that absolute path in `book_run_summary.json` as `ledger_data_root`. Resuming the same run ID reuses those ledgers so staged `20 -> 30 -> 40 -> 50` continuation does not lose prior scene metrics. Starting a different run ID gets an isolated ledger root. Using `--force` removes that run ID's ledger root before regeneration.

The Author Dashboard book-level endpoints prefer `book_run_summary.ledger_data_root` when present, so `GET /books/{book_id}/ledgers`, metric history, character metrics, promise, intimacy, and quality-gate reads match the generated run artifact instead of any stale shared proof-run ledgers. Older summaries that predate `ledger_data_root` remain readable but cannot retroactively provide run-local ledger history.

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
- `configured_data_root` and `ledger_data_root`; production full-book runs use the run-local ledger root for mutable ledger state.
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
make run-full-book RUN_BOOK_ARGS="\
  --config data/series/cedar-harbor-romance/pipeline_config.json \
  --series-id cedar-harbor-romance \
  --book-id book01 \
  --run-id cedar-harbor-book01-test \
  --model-tier test \
  --provider openai \
  --max-scenes 1"
```

Run the first three scenes by changing `--max-scenes 1` to `--max-scenes 3`. The legacy one-scene orchestrator path (`python -m pipeline.orchestrator --job ch01_sc01 ...`) remains available for debugging, but unattended production runs should use `make run-full-book` so resume, force, summary, eval, verifier, and dashboard checks share one contract.

Keep `model_router.json` defaulted to `test`; `run_full_book.py` writes `model_router.run.json` under the run directory for explicit tier selection.

Post-fix Cedar Harbor proof, 2026-06-15:

```bash
make run-full-book RUN_BOOK_ARGS="\
  --config data/series/cedar-harbor-romance/pipeline_config.json \
  --series-id cedar-harbor-romance \
  --book-id book01 \
  --run-id cedar-harbor-book01-wordcount-fix \
  --model-tier test \
  --provider openai \
  --max-scenes 3"
```

Result: expected `FAIL` after the new guard. The run generated three scenes at production-scale lengths (`1320`, `1441`, `1220` words against `1300` targets), proving the underlength prompt/quality loop works. One scene exhausted quality retries and force-resolved due structural quality flags, so the unattended runner correctly failed the run instead of silently accepting it. Cost: `60541` tokens, `$0.02145795` estimated.

Follow-up diagnosis: `ch01_sc02` had 7 medium structural flags in 1441 words. The old `QualityAgent` gate used an absolute `structural <= 6` warn threshold, which became brittle once scenes expanded to production length. The gate is now length-aware: floor `6`, then `ceil(6 flags per 1000 words)` for longer scenes. This would classify the observed `ch01_sc02` case as warn/GO while still failing dense structural issue clusters.

Validation proof after the length-aware structural threshold:

```bash
make run-full-book RUN_BOOK_ARGS="\
  --config data/series/cedar-harbor-romance/pipeline_config.json \
  --series-id cedar-harbor-romance \
  --book-id book01 \
  --run-id cedar-harbor-book01-quality-tune \
  --model-tier test \
  --provider openai \
  --max-scenes 3"
```

Result: `PASS`. The first invocation was interrupted by the tool timeout during `ch02_sc01`; rerunning the same command resumed correctly, skipped completed scenes 1-2, and finished scene 3. Final summary: `3/3` GO, `0` force-resolved, verifier skipped as `partial_run`, eval PASS over exactly `3` selected scenes, dashboard summary PASS, `3795` assembled words, `64841` tokens, `$0.02289585` estimated. Scene word counts: `1303`, `1184`, `1308`; `1184` is above the current 90% minimum for a 1300-word target.

Ten-scene continuation result:

```bash
make run-full-book RUN_BOOK_ARGS="\
  --config data/series/cedar-harbor-romance/pipeline_config.json \
  --series-id cedar-harbor-romance \
  --book-id book01 \
  --run-id cedar-harbor-book01-quality-tune \
  --model-tier test \
  --provider openai \
  --max-scenes 10"
```

Result: expected `FAIL` after exposing a new issue. The run resumed correctly, skipped scenes 1-3, generated scenes 4-10, and ended with `9/10` GO, `1` force-resolved (`ch05_sc01`), eval FAIL, dashboard PASS, verifier skipped as `partial_run`, `12556` assembled words, `215374` tokens, `$0.0757437` estimated. Diagnosis: `ch05_sc01` was structurally within the scaled warn threshold but the editor's structural surgical edit shrank an above-target writer draft to `1165` words, 5 words below the 90% floor (`1170`). The final text also contained an appended alternate-version separator (`---`). Follow-up fix: `EditorAgent` now rejects structural-only surgical edits that shrink an already-above-minimum draft below the floor; NoFly cleanup can still shrink and route through normal quality retry. `WriterAgent` retry prompts now explicitly prohibit Markdown separators and alternate appended versions.

Fresh proof after the editor length guard:

```bash
make run-full-book RUN_BOOK_ARGS="\
  --config data/series/cedar-harbor-romance/pipeline_config.json \
  --series-id cedar-harbor-romance \
  --book-id book01 \
  --run-id cedar-harbor-book01-editor-guard \
  --model-tier test \
  --provider openai \
  --max-scenes 10"
```

Result: expected `FAIL` after exposing the next root cause. The editor guard fixed the prior `ch05_sc01` failure: `ch05_sc01` routed GO at `1270` words. The run still ended with `9/10` GO, `1` force-resolved (`ch03_sc02`), eval PASS over exactly `10` selected scenes, dashboard summary PASS, verifier skipped as `partial_run`, `13184` assembled words, `204805` tokens, `$0.0719106` estimated. Diagnosis: `ch03_sc02` had `0` NoFly violations and `0` structural issues, but actual final/status word count was `1008`, below the `1170` minimum. Writer logs and memory were trusting model-reported counts around `1318` words, so the runtime appeared to be expanding successfully while the actual text remained underlength. Follow-up fix: `WriterAgent` now recomputes every `WriterOutput.word_count` from `draft_text`, overwrites the model-reported value, normalizes `scene_id` to `JobContext.scene_id`, and tells retry prompts the previous draft's actual word count plus the minimum additional words needed.

## Next Forward-Progress Approval Packet

Use this packet when the author wants one approval to move the Cedar Harbor proof forward instead of approving one tiny live step at a time.

Approval language:

```text
Approved: run the Cedar Harbor forward-progress batch on test tier only, cap estimated live spend at $0.50, progress 10 -> 20 -> 30 -> 40 -> 50 scenes when gates pass, and use one scoped fix-and-retry cycle if a stage exposes a deterministic runner/agent bug. No production tier.
```

Authorized by that single approval:

- Preflight with no live spend: inspect status, confirm `model_router.json` is still `test`, run `make lint && OPENAI_API_KEY= ANTHROPIC_API_KEY= make test` if source changed since the last green suite.
- Start fresh run ID `cedar-harbor-book01-writer-count` at `--max-scenes 10` on `test/openai`.
- If partial gates pass, continue the same run ID with `--max-scenes 20`, then `30`, then `40`, then `50`. Resume skips already-completed scenes.
- If a tool timeout interrupts a live stage, rerun the same command once to resume without asking again.
- If a stage fails due to a deterministic code issue in the runner, `WriterAgent`, `EditorAgent`, or `QualityAgent`, diagnose from artifacts, implement the smallest source fix, run no-live tests, then retry that same stage once with a fresh run ID suffix.

Automatic continue gates for partial stages (`10`, `20`, `30`, `40`):

- `run_passed = true`
- `force_resolved_scenes = 0`
- deterministic eval passes for exactly the selected scene paths
- dashboard summary check passes
- no unexpected stale-scene eval globbing or summary inconsistency
- estimated cost remains below the packet cap

Full-stage gate (`50`):

- all partial gates pass
- `BookStructuralVerifier` runs because this is no longer a partial run
- if verifier fails, stop after diagnosis and record whether the failure is word-count, structure, heat-curve, required-slot, or another check

Stop and ask before continuing if any of these occur:

- estimated live spend would exceed `$0.50`
- production tier or Anthropic production models would be used
- a fix would loosen sensitivity, quality, or content-policy gates rather than correcting measurement/routing behavior
- a fix requires new dependencies, new services, or schema/profile changes
- two live failures occur at the same stage after one scoped fix-and-retry cycle
- the required next step is story/content judgment rather than deterministic pipeline behavior

Canonical staged command, changing only `--max-scenes` as gates pass:

```bash
make run-full-book RUN_BOOK_ARGS="\
  --config data/series/cedar-harbor-romance/pipeline_config.json \
  --series-id cedar-harbor-romance \
  --book-id book01 \
  --run-id cedar-harbor-book01-writer-count \
  --model-tier test \
  --provider openai \
  --max-scenes 10"
```

Forward-progress batch result, 2026-06-16:

- Preflight: root `model_router.json` and Cedar Harbor `pipeline_config.json` both confirmed `test/openai`; `make lint` passed.
- Stage `cedar-harbor-book01-writer-count --max-scenes 10`: `PASS`, `10/10` GO, `0` force-resolved, eval PASS over exactly `10` scenes, dashboard summary PASS, verifier skipped as `partial_run`, cost `$0.0619731` / `175062` tokens.
- Stage `cedar-harbor-book01-writer-count --max-scenes 20`: `FAIL`, but with useful signal: `20/20` GO and `0` force-resolved, dashboard summary PASS, verifier skipped as `partial_run`; deterministic eval failed on `ch08_sc02` with `AITellMetric=0.4215`. Cost for that run ID at failure: `$0.1220286` / `344147` tokens.
- Diagnosis: live `QualityAgent` used raw structural flag count for warn/GO, while offline `AITellMetric` scores weighted structural density. `ch08_sc02` had enough weighted structural density to fail eval while still fitting the raw length-aware count threshold.
- Scoped fix: `QualityAgent` now gates on both raw structural count and `EditorOutput.structural_weighted_score`. Weighted warn threshold is aligned to offline eval pass behavior: about `5` weighted structural points per `1K` words, with a floor of `5`. Regression test: `test_structural_weighted_threshold_aligns_with_ai_tell_eval`.
- Verification after scoped fix: focused tests passed, `make lint` passed, and no-live full suite passed with `395 passed, 6 skipped`.
- Retry `cedar-harbor-book01-writer-count-ai-tell --max-scenes 20`: stopped early because OpenAI returned `429 insufficient_quota`. Partial retry artifact: `5/20` GO, `1` force-resolved before the writer-node quota error, dashboard summary PASS, cost `$0.0322014` / `91715` tokens. Live progression stopped; no production tier was used.
- Additional fail-closed fix from retry: `SceneStateMachine` now stops immediately on writer/editor/continuity/quality node exceptions instead of continuing downstream after `error` is set. Regression test: `test_writer_exception_stops_before_editor_quality_and_final`.
- Final no-live verification after fail-closed fix: `make lint` passed and `OPENAI_API_KEY= ANTHROPIC_API_KEY= make test` passed with `396 passed, 6 skipped`.
- User approved Anthropic test tier as the fallback provider after OpenAI quota exhaustion. Anthropic stage `cedar-harbor-book01-weighted-gate-anthropic --max-scenes 20` passed: `20/20` GO, `0` force-resolved, eval PASS over exactly `20` scenes, dashboard summary PASS, verifier skipped as `partial_run`, `26441` assembled words against 26000 planned selected-scene words, `$0.4984488` / `233001` tokens.
- User approved an additional `$5` Anthropic test-tier cap. Continuation `--max-scenes 30` passed: `30/30` GO, `0` force-resolved, eval PASS, dashboard PASS, verifier skipped as `partial_run`, `39077` assembled words, cumulative cost `$0.6903` / `320703` tokens.
- Continuation `--max-scenes 40` passed: `40/40` GO, `0` force-resolved, eval PASS, dashboard PASS, verifier skipped as `partial_run`, `52633` assembled words, cumulative cost `$0.9024768` / `416828` tokens.
- Full stage `--max-scenes 50` passed: `50/50` GO, `0` force-resolved, eval PASS over all 50 scenes, dashboard summary PASS, strict `BookStructuralVerifier` PASS, final manuscript word count `64982` against the 65000-word target, cumulative cost `$1.153952` / `534840` tokens.

The full Cedar Harbor `book01` test-tier proof is complete. Do not run further live regeneration, production tier, or provider comparison without a new explicit approval. OpenAI remains blocked by `429 insufficient_quota`; any future OpenAI retry should use a fresh run ID because `cedar-harbor-book01-writer-count-ai-tell` contains partial quota-failure artifacts.

No-live hardening after the full proof, 2026-06-17:

- Root cause fixed: staged full-book runs no longer write mutable ledger state into the shared configured ledger root. The runner now writes ledgers under `runs/{run_id}/ledgers/` and records `ledger_data_root` in the summary.
- Regression coverage: `./.venv/bin/pytest tests/unit/test_full_book_runner.py tests/unit/api/test_dashboard_api.py` passed with `30 passed`. Tests cover run-ID isolation, staged resume without double-counting (`2 -> 3 -> 4` standing in for `20 -> 30 -> 40`), `--force` ledger reset behavior, and dashboard summary-aware ledger resolution. Final no-live gate also passed: `make lint` clean and `OPENAI_API_KEY= ANTHROPIC_API_KEY= make test` returned `400 passed, 6 skipped`.
- Dashboard dogfood against the existing Cedar Harbor summary: summary read succeeded with `summary_found = true`, `run_passed = true`, and `total_word_count = 64982`. That existing summary predates `ledger_data_root`, so ledger endpoints correctly cannot reconstruct run-local ledger history from it.
- EvoSkill dogfood: `OPENAI_API_KEY= ANTHROPIC_API_KEY= ./.venv/bin/python scripts/evoskill_nightly.py --data-root "data/series/cedar-harbor-romance/data/ledgers"` found `29` Cedar Harbor failure traces in the last 24 hours and promoted one local skill under the gitignored ledger tree.

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
