# Task 014 — Production Hardening + Model Promotion

```
status: pending
started:
completed:
phase: 14
estimated_hours: 10-14
depends_on: task-013
```

## Goal

DeepEval CI quality gates (VoiceConsistencyMetric, AI-Tell metric). LangGraph checkpoint persistence (pause/resume survives process kill). Mem0 integration for semantic bible retrieval. Claude Files API for series bible upload. Full 3-scene integration test. Model tier promotion to production (Sonnet 4.6 drafter / Opus 4.7 critics). First end-to-end production run.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 14 (Production Hardening + Model Promotion)

## Dependencies

- task-013 (Author Dashboard — full pipeline is running; all ledgers active)
- task-008 (VoiceExemplarManager — VoiceConsistencyMetric uses it as a scoring reference)
- task-007 (LangGraph scene state machine — checkpoint persistence configured here)

## Acceptance criteria

- [ ] `tests/eval/voice_consistency_metric.py` — DeepEval `VoiceConsistencyMetric`: Claude scores generated prose against voice profile; configurable threshold per genre
- [ ] `tests/eval/ai_tell_metric.py` — DeepEval metric: AI-tell density per 1K words; uses structural_analysis.py deterministically + optional LLM-as-judge for severity-5 tells
- [ ] `make eval` runs both metrics against the last completed scene without errors
- [ ] VoiceConsistencyMetric produces a numeric score (0–1); score is logged
- [ ] AI-Tell metric produces severity-weighted density score; below-threshold scene flagged
- [ ] LangGraph checkpoint persistence: pause mid-scene (kill process); restart from checkpoint; scene continues from paused state without re-running completed agents
- [ ] LangGraph checkpoint resume test passes
- [ ] Mem0 integration: voice profile + accumulated character facts seeded into Mem0 at series init
- [ ] Agents retrieve relevant facts via Mem0 semantic search (not full bible injection into context)
- [ ] Claude Files API integration: series bible (WUPHF wiki export), voice profile, character sheets uploaded once per series init; agents reference by file_id
- [ ] Full 3-scene integration test (test tier): all 10 ledgers updated, BibleSteward active, ConvergenceController routing correctly; run completes under 5 minutes
- [ ] **Model tier promotion:** `model_router.json` `model_tier = "production"`; 3-scene integration test run with production models (claude-sonnet-4-6 drafter, claude-opus-4-7 critics)
- [ ] Production run comparison: prose quality vs test-tier run noted; differences logged to DECISIONS.md
- [ ] CI: `make test && make eval` passes on clean checkout
- [ ] Smoke test pass criteria met: one agent accepts spec, calls LLM, returns structured output matching schema, no errors, under 60 seconds (already met in Phase 7; re-verify with production models)

## Subtasks

- T14.1 — Implement `tests/eval/voice_consistency_metric.py`. Class `VoiceConsistencyMetric(BaseMetric)` extending DeepEval's BaseMetric. `measure(test_case: LLMTestCase) → float`: (1) Load VoiceProfile for the series. (2) Call Claude (via ModelRouter, test tier unless --production flag) with structured prompt: "Score this prose 0–1 for adherence to the voice profile. Profile: {voice_axes}. Prose: {generated_prose}. Return JSON: {score: float, rationale: string}". (3) Use Instructor for structured output. (4) Return score. Threshold: configurable per genre (Romance default 0.75, Erotica default 0.70 — more kinetic prose expected).
- T14.2 — Implement `tests/eval/ai_tell_metric.py`. Class `AITellMetric(BaseMetric)`. `measure(test_case: LLMTestCase) → float`: (1) Call `structural_analysis.scan_ai_tells(prose)` (deterministic — counts all AI-tell patterns from ai_tell_catalog). (2) Compute severity-weighted density: `sum(severity * count for each pattern) / (word_count / 1000)`. (3) For any pattern with severity 5: optionally call LLM-as-judge for confirmation. (4) Return normalized score (0 = clean, 1 = severe). Threshold: genre-specific from genre_profile.quality_gates where metric == "ai_tell_density".
- T14.3 — DeepEval CI integration: add `make eval` Makefile target: `python -m deepeval test run tests/eval/ --output-file data/eval_results.json`. Log score + pass/fail to DECISIONS.md on each run. Optional pre-commit hook: warn (do not block) if eval score drops below threshold.
- T14.4 — LangGraph checkpoint persistence: configure `langgraph.checkpoint.sqlite.SqliteSaver` at `data/{series_id}/checkpoints/{run_id}.db`. Test: (a) Start a 3-scene run. (b) After scene 1 completes, send SIGKILL to process. (c) Restart orchestrator with `--resume {checkpoint_id}`. (d) Assert scene 2 starts (scene 1 not re-run). (e) Assert final output matches what a full run would produce.
- T14.5 — Mem0 integration: `pipeline/memory/mem0_client.py`. Mem0Client (self-hosted): `seed_series(series_id: str, voice_profile: VoiceProfile, bible: BibleState)`: upload series context to Mem0 at series init. `retrieve(query: str, series_id: str, n: int = 5) → list[MemoryFact]`: semantic search for relevant facts. Integrate into ContextManager: replace full-bible-injection with Mem0 retrieval for book-tier context (inject top-5 semantically relevant facts instead of entire bible). Reads MEM0_HOST from `.env`.
- T14.6 — Claude Files API integration: `pipeline/memory/files_api_client.py`. FilesAPIClient: `upload_series_bible(bible_path: Path, series_id: str) → str` (returns file_id). `upload_voice_profile(profile_path: Path, series_id: str) → str`. `upload_character_sheets(char_dir: Path, series_id: str) → dict[str, str]` (char_id → file_id). Store file_ids in `data/{series_id}/file_ids.json`. Agents reference bible sections by file_id in their API calls (reduces token cost for long-running series). Requires ANTHROPIC_API_KEY.
- T14.7 — Full 3-scene integration test (test tier): `tests/integration/test_3scene_integration.py`. Fixture: Romance Module v1 spec, 3 consecutive scenes (1.1, 1.2, 1.3). Test: (a) `--init-book` → scene inventory. (b) `--job scene_1_1` → FINAL. (c) `--job scene_1_2` → FINAL. (d) `--job scene_1_3` → FINAL. (e) Assert: all 10 ledgers updated after each scene, BibleSteward has 3+ commits, ConvergenceController history has no unexpected FORCE-RESOLVE entries, total elapsed < 5 minutes. (f) `--verify-book` → VerificationReport with no critical failures.
- T14.8 — **Model tier promotion:** (1) Set `model_router.json` `model_tier = "production"`. (2) Run T14.7 integration test with production models. (3) Compare: prose word count, voice_consistency_metric score, ai_tell_metric score vs test-tier run. (4) Log observations to DECISIONS.md: "Production run 2026-XX-XX: VoiceConsistency={score}, AITell={score}, prose_word_count={n}, notes={...}". (5) Set `model_router.json` back to `"test"` unless user explicitly chooses to leave it on production. Note: production tier is expensive — only run this test when architecturally stable.
- T14.9 — Write `tests/unit/eval/test_eval_metrics.py`: VoiceConsistencyMetric produces a float score 0–1 (mock Claude call). AITellMetric correctly computes severity-weighted density on fixture prose (deterministic path; no LLM mock needed). Threshold comparison test: above-threshold scene passes, below-threshold scene fails.
- T14.10 — Update `runbooks/production-run.md`: document full production run sequence (series init → Mem0 seed → Files API upload → `--init-series` → `--init-book` → `--job` loop → `--verify-book` → `make eval` → `--book-publish`).
- T14.11 — Commit: `feat(hardening): DeepEval metrics, LangGraph checkpoint persistence, Mem0, Files API, production model promotion (task-014)`.

## Key decisions that affect this task

- **Model tiering promotion here and only here (DEC-009):** Phase 14 is the only phase where `model_router.json` is changed to `"production"`. All prior phases use test tier. After the production run comparison, the user decides whether to keep production or revert to test.
- **DeepEval CI integration:** `make eval` runs the metrics; it does not block `make test`. Separation keeps the test suite fast and the eval suite accurate.
- **Mem0 replaces full-bible-injection:** The ContextManager book-tier context switches from injecting the entire bible to Mem0 semantic retrieval of the 5 most relevant facts. This reduces token cost at scale and is the motivation for the integration.
- **Claude Files API reduces per-call cost:** Upload once per series init; reference by file_id in subsequent calls. Not needed for V1 short runs but critical for 100K-word novels.
- **LangGraph checkpoint is the resume mechanism (decisions.md 2026-05-15):** The SQLite checkpoint store survives process kill. `--resume` is the user-facing command. Temporal (durable execution) is V2 if this proves insufficient.
- **3-scene test under 5 minutes (test tier):** This is the plan's smoke test pass criterion for a multi-scene run. Production tier may be slower — acceptable.

## Suggested approach

1. Implement VoiceConsistencyMetric + AITellMetric; test with fixture data.
2. Add `make eval` target; verify it runs.
3. Configure LangGraph checkpoint persistence; write resume test.
4. Implement Mem0Client + integrate into ContextManager.
5. Implement FilesAPIClient.
6. Write 3-scene integration test; run with test-tier models.
7. Promote to production models; run comparison; log to DECISIONS.md.
8. Update production run runbook.
9. Commit.

## Decisions to log in DECISIONS.md

- VoiceConsistencyMetric threshold per genre (Romance 0.75, Erotica 0.70 — log rationale).
- AITellMetric LLM-as-judge threshold (severity 5 only — log why not 4).
- Mem0 retrieval N (top-5 facts — log chosen value).
- Files API cache invalidation policy (re-upload on each series init vs track version — log choice).
- Production run comparison results (required — captures the first real quality data point).

## Notes

- DeepEval (`confident-ai/deepeval`) is a confirmed adopt tool (decisions.md 2026-05-15). Read its docs for custom metric API: `class VoiceConsistencyMetric(BaseMetric)` with `measure()`, `is_successful()`, `score`.
- The VoiceConsistencyMetric uses Claude to score prose — it is an LLM-as-judge pattern. Use test tier for CI to keep eval fast and cheap.
- The production model run in T14.8 is the first time Sonnet 4.6 (drafter) and Opus 4.7 (critics) touch the pipeline. Expect prose quality to improve noticeably. The comparison is the evidence base for the user's production investment decision.
- Mem0 is self-hosted (local dev). Reads MEM0_HOST from `.env`. If Mem0 is not running, ContextManager falls back to full-bible-injection (graceful degradation with a log warning).

## Out of scope

- Ensemble drafting (V2 roadmap — Phase 15)
- Drafter D fine-tuning (V2 roadmap)
- harbor eval ratcheting (V2 roadmap — replaces DeepEval at scale)
- Signing / watermarking (V2 roadmap)
- V2 scope items of any kind
