# Full-Book Generation Turn Prompts

Use these prompts for new coding sessions. Start with Turn 1. Each turn tells the agent to continue into the next turn if it completes cleanly.

## Common Instructions For Every Turn

Paste this preamble with any turn prompt if you are starting in a fresh session:

```text
You are working in /home/gosne/src/workspace/Systems Architecture.

Goal: get Fiction-Factory from the current Phase 14 green state to repeatable full-book generation.

Start by checking git status, reading the current repo state, and respecting existing CLAUDE.md, ARCHITECTURE.md, IMPLEMENTATION_PLAN.md, DECISIONS.md, and SESSION_REGISTRY.md instructions. Do not revert user or other-agent changes. Use apply_patch for edits. Keep changes minimal and coherent.

Preserve the default development posture: model_router.json stays defaulted to test. Production-tier runs must use run-local config or explicit command flags, never mutate the default router config.

Do not write secrets. Do not commit or push unless I explicitly ask in this session. If a live model run would spend API credits, run it only when the turn explicitly asks for live acceptance; otherwise use mocked tests.

Verification expectation: run targeted tests for changed code, make lint, and make test when the change touches shared pipeline paths. Update DECISIONS.md, SESSION_REGISTRY.md, and relevant runbooks when adding a durable workflow decision.

Auto-continue rule: if you complete the current turn with passing verification and no blockers, read docs/runbooks/full-book-generation-turn-prompts.md and continue immediately into the next turn prompt. If the next turn requires live API spend, human author input, or a production decision, stop and report instead of continuing.
```

## Turn 1 Prompt: Full-Book Runner And Short-Book Fixture

```text
Turn 1 objective: implement the first repeatable full-book runner and a short-book fixture. This turn should make it possible to run all scenes for a small book through the same JobRunner path used by Phase 14 scene acceptance, but it should not spend live model/API credits in tests.

Current relevant state:
- scripts/run_phase14_acceptance.py exists and passes 3-scene test-tier and production-tier acceptance.
- make phase14-acceptance exists.
- scripts/run_eval.py supports --scene-dir, --require-scenes, and --max-scenes.
- JobRunner handles one scene, checkpoints, dashboard events, EvoSkill traces, ledgers, continuity, and final scene output.
- BookStructurePlanner and BookStructuralVerifier exist.
- data/phase14_acceptance/ is ignored.

Tasks:
1. Inspect BookStructurePlanner, BookStructuralVerifier, ProjectLayout, JobRunner, orchestrator book flow, and Phase 14 acceptance runner before editing.
2. Add a reusable book-level runner, preferably pipeline/book_runner.py, that accepts a ProjectSpec, a scene inventory or fixture scene list, AgentContext/ModelRouter setup, and runs scenes in order through JobRunner.
3. Keep the runner resumability-friendly from the start: record scene status, output paths, convergence decision, revise count, force-resolved flag, word count, elapsed time, and errors for each scene.
4. Add a thin script, likely scripts/run_book_acceptance.py, with a short Romance Module fixture of 6-12 scenes and small word targets. The script should default to test tier and write under data/book_acceptance/ or data/full_book_acceptance/. Add that generated data path to .gitignore.
5. Add a Makefile target, likely make book-acceptance, that invokes the script.
6. Do not require live LLM calls in automated tests. Add tests with a fake JobRunner or monkeypatched agents to prove the book runner executes all fixture scenes in order and records statuses.
7. It is okay if Turn 1 only writes individual scene files and a basic run status. Turn 2 will harden ordered manuscript assembly and book_run_summary.json.
8. Update docs/runbooks with the new command and update DECISIONS.md and SESSION_REGISTRY.md if you add a durable workflow decision.

Acceptance:
- The new book runner has targeted tests that pass without API keys.
- make lint passes.
- make test passes if shared pipeline code was changed.
- No generated book acceptance data is tracked by git.
- model_router.json remains defaulted to test.

If this turn completes cleanly, continue into Turn 2 from docs/runbooks/full-book-generation-turn-prompts.md without asking me first. Stop instead if you need live API spend, a schema decision, or author input.
```

## Turn 2 Prompt: Ordered Manuscript Assembly And Book Summary

```text
Turn 2 objective: turn a completed short-book scene run into an ordered manuscript and durable book_run_summary.json.

Tasks:
1. Inspect the Turn 1 book runner output and existing ProjectLayout.manuscript_path().
2. Add ordered manuscript assembly from finalized scene files, using scene inventory order. Missing scene files should fail clearly.
3. Add chapter/scene headings in manuscript.md with stable, deterministic formatting.
4. Add book_run_summary.json with run ID, model tier, provider, scene statuses, total word count, GO count, force-resolved count, failed scene IDs, elapsed time, manuscript path, scene directory, ledger dashboard summary, eval status if available, and verifier status if available.
5. Add tests for correct ordering, missing scene failure, and summary content.
6. Wire assembly into the book acceptance script.
7. Update docs/runbooks and SESSION_REGISTRY.md. Add a DECISIONS.md entry only if you define a durable summary/assembly contract.

Acceptance:
- A mocked short-book run writes manuscript.md and book_run_summary.json.
- Tests cover ordering and missing scene handling.
- make lint passes.
- make test passes if shared pipeline code was changed.

If this turn completes cleanly, continue into Turn 3. Stop instead if the runner output from Turn 1 is missing or incompatible.
```

## Turn 3 Prompt: Resume And Skip Final Scenes

```text
Turn 3 objective: make book-level runs resumable and idempotent.

Tasks:
1. Add resume/skip behavior to the book runner: if a scene already has a final output and status says it completed, skip it unless --force is passed.
2. Preserve failed scene information and allow rerun from the first failed/incomplete scene.
3. Make checkpoint thread IDs visible in the book summary for every scene.
4. Add CLI flags for --resume and --force, or equivalent minimal flags that match current conventions.
5. Add tests for a first run that fails mid-book, a second run that skips completed scenes, and a force rerun that regenerates all scenes.
6. Update docs/runbooks and SESSION_REGISTRY.md. Add DECISIONS.md if you lock a resume contract.

Acceptance:
- Re-running the same short-book fixture does not rerun completed scenes by default.
- --force or equivalent reruns scenes intentionally.
- Failed/incomplete scenes are easy to identify in summary JSON.
- make lint and relevant tests pass.

If this turn completes cleanly, continue into Turn 4 only if live test-tier API spend is acceptable in this session. If not, stop and report that Turn 4 is the next live acceptance run.
```

## Turn 4 Prompt: Live Short-Book Test-Tier Acceptance

```text
Turn 4 objective: run a live test-tier short-book acceptance and fix code blockers.

Tasks:
1. Run the short-book acceptance command from the runbook using test tier and the default cheap provider.
2. Run corpus eval over the generated scene directory with --require-scenes matching the fixture scene count.
3. Run BookStructuralVerifier if it is not already wired into the book summary.
4. Inspect generated manuscript.md, book_run_summary.json, ledger totals, dashboard event files, and EvoSkill traces.
5. Fix only code/workflow issues. Do not tune prose quality unless the failure is caused by a deterministic gate bug.
6. Record results in docs/runbooks and DECISIONS.md if this establishes the first short-book acceptance pass.

Acceptance:
- Live short-book run completes.
- All scenes reach GO or failures are understood and documented.
- manuscript.md exists and is ordered.
- book_run_summary.json exists.
- corpus eval passes or failures are actionable.
- make lint and targeted tests pass after any fixes.

If this turn completes cleanly, continue into Turn 5. Stop if live credentials are unavailable or the run fails for model/API reasons outside code control.
```

## Turn 5 Prompt: Files API And Real Token/Cost Accounting

```text
Turn 5 objective: reduce context bloat and make model-cost comparisons real.

Tasks:
1. Inspect ModelRouter, existing cost_log.jsonl behavior, memory/files API clients, AgentContext managed config, and ContextPackBuilder.
2. Add real token usage extraction for OpenAI and Anthropic responses in ModelRouter cost logs. Preserve graceful fallback if usage fields are missing.
3. Add tests for token/cost logging using mocked provider responses.
4. Wire Claude Files API support for series bible, voice profile, and character sheets at series/book init or book-run setup, using existing approved client patterns where possible.
5. Ensure file IDs are stored in run-local metadata, not secrets or source files.
6. Update runbooks and decisions if this locks the cost-log schema or Files API lifecycle.

Acceptance:
- Cost logs contain nonzero token counts in mocked tests.
- Existing ModelRouter tests still pass.
- Files API hooks can be exercised without live secrets through mocks.
- make lint and make test pass.

If this turn completes cleanly, continue into Turn 6 only if live test-tier novella generation is acceptable. Otherwise stop and report.
```

## Turn 6 Prompt: Live Test-Tier Novella And Dashboard Check

```text
Turn 6 objective: run a longer test-tier novella and verify the author-facing artifacts.

Tasks:
1. Create or extend a 12-20 scene novella fixture using the full-book runner.
2. Run it with test-tier models.
3. Run corpus eval and BookStructuralVerifier.
4. Start or inspect the dashboard API against the generated data root. Browser testing is optional; API-level checks are required.
5. Verify book_run_summary.json includes cost totals, eval, verifier result, ledger summary, and scene statuses.
6. Fix deterministic code/workflow issues only.
7. Record results in docs/runbooks and SESSION_REGISTRY.md.

Acceptance:
- Test-tier novella completes or fails with actionable code issues.
- Dashboard API can read the generated ledgers/events.
- Eval and verifier results are recorded.
- make lint and relevant tests pass after fixes.

If this turn completes cleanly, continue into Turn 7. Stop if live generation cost or runtime needs user approval.
```

## Turn 7 Prompt: EvoSkill Nightly Passes And Promotion

```text
Turn 7 objective: prove learning loop closure on real full-book or novella traces.

Tasks:
1. Run scripts/evoskill_nightly.py over the latest novella/full-book traces.
2. Run at least 3 passes if the script supports repeated local execution, or simulate repeated passes with distinct fixture traces if needed.
3. Verify failure traces and revised-then-GO traces are classified correctly.
4. Verify accepted skills are written locally and promoted to WUPHF local wiki when configured.
5. Add or update tests for any breakage found.
6. Record promoted skills and results in docs/runbooks and SESSION_REGISTRY.md.

Acceptance:
- EvoSkill nightly command runs on real traces.
- At least one accepted/promoted skill exists, or the no-promotion result is explicitly explained.
- make lint and targeted tests pass.

If this turn completes cleanly, continue into Turn 8 only if production-tier live spend is acceptable. Otherwise stop and report.
```

## Turn 8 Prompt: Production-Tier Novella Comparison

```text
Turn 8 objective: compare production-tier novella output against test-tier output using the same spec.

Tasks:
1. Run the same novella spec with production-tier models using run-local router config. Do not mutate model_router.json.
2. Run corpus eval and BookStructuralVerifier.
3. Compare test-tier vs production-tier: runtime, cost, word count, GO/revise decisions, eval scores, verifier result, and a small prose sample note.
4. Record the comparison in docs/runbooks and DECISIONS.md.
5. Recommend production defaults per role if evidence supports it, while keeping development default test-tier.

Acceptance:
- Production-tier novella run completes or fails with a clear blocker.
- Comparison report exists.
- model_router.json remains defaulted to test.
- make lint and targeted tests pass after any code changes.

If this turn completes cleanly, continue into Turn 9 only if the author has provided or approved a real full-book spec. Otherwise stop and ask for the real series/book spec.
```

## Turn 9 Prompt: First Full-Length Book Run

```text
Turn 9 objective: run the first full-length book through the pipeline.

Tasks:
1. Confirm the author-approved series_spec and book_spec exist. If they do not, stop and ask for them.
2. Validate specs and reject sentinel strings.
3. Generate or load the full scene inventory.
4. Run the full-book runner with checkpoint/resume enabled.
5. Assemble manuscript.md and book_run_summary.json.
6. Run corpus eval, BookStructuralVerifier, and dashboard artifact checks.
7. Run EvoSkill nightly passes over the full-book traces if runtime is acceptable.
8. Produce a line-editor packet: manuscript path, summary path, verifier report, eval report, ledger dashboard summary, known caveats.
9. Do not publish. Human line-editor review remains a permanent gate.

Acceptance:
- Full manuscript exists as ordered manuscript.md.
- Book summary includes scene, cost, eval, verifier, and ledger results.
- Any failures are bounded and actionable.
- Human line-editor packet is ready.

If this turn completes cleanly, stop and report that V1 has reached first full-book generation readiness. Do not continue into V2 work.
```
