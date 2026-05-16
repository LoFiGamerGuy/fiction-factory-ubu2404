# Task 009 — Bible + Continuity Layer

```
status: pending
started:
completed:
phase: 9
estimated_hours: 8-12
depends_on: task-007
```

## Goal

BibleSteward (propose/validate/commit deltas with atomic writes and content-hash chain), LoopTracker (Promise + Series Promise Ledger deadline enforcement), and integration with the Convergence Controller so that Bible contradictions → RE-PLAN and overdue promises → REVISE.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 9 (Bible + Continuity Layer)

## Dependencies

- task-007 (ConvergenceController — BibleSteward integrates with it; scene state machine must be running)
- task-003 (PromiseLedger, SeriesPromiseLedger — LoopTracker writes to these ledgers)
- task-002 (continuity_model.schema.json — BibleSteward validates deltas against this schema)

## Acceptance criteria

- [ ] `pipeline/continuity/bible_steward.py` — `propose_delta`, `validate_delta` (6 contradiction types), `commit_delta` (atomic os.replace + exclusive lock + append-only event log + content-hash chain + per-book snapshot), `query`
- [ ] BibleSteward: `validate_delta` detects all 6 contradiction types: type-mismatch, timeline-violation, spatial, capability, voice, taboo
- [ ] BibleSteward: `commit_delta` is atomic — uses `os.replace()` + exclusive file lock; no partial writes survive a crash
- [ ] BibleSteward: append-only event log — every commit appended to `{book_id}/bible_events.jsonl`
- [ ] BibleSteward: content-hash chain — each event's hash includes previous event's hash (like a blockchain link)
- [ ] BibleSteward: per-book snapshot — `commit_delta` writes current bible state to `{book_id}/bible_snapshot_{n}.json`
- [ ] BibleSteward contradiction test: commit a delta that conflicts with existing fact → rejected with contradiction type identified
- [ ] `pipeline/continuity/loop_tracker.py` — `enforce_promise_deadlines(chapter: int) → list[OverduePromise]`; `enforce_series_threads(book: int) → list[OverdueSeriesPromise]`; `no chapter ships with overdue promises` enforced
- [ ] LoopTracker overdue test: chapter 15 attempted with an overdue promise (deadline = chapter 12) → returns OverduePromise, Convergence Controller routes to REVISE
- [ ] Port manus-agnostic `continuity_agent.py` to BibleSteward/LoopTracker architecture
- [ ] Port manus-agnostic `series_arc_tracker.py`; extend to write to SeriesPromiseLedger
- [ ] Series arc update failure is fatal: `series_arc_tracker.update()` raises; pipeline does not continue (MBSE policy)
- [ ] Convergence Controller integration: Bible contradiction → RE-PLAN (hard fail); overdue promise → REVISE up to max_revisions, then RE-PLAN
- [ ] Integration test: full scene runs with BibleSteward active; after scene, bible is updated; contradiction in next scene's delta is detected before committing
- [ ] `make test` passes

## Subtasks

- T9.1 — Implement `pipeline/continuity/bible_steward.py`. BibleSteward class:
  - `__init__(project_layout: ProjectLayout, continuity_schema_path: Path)`: loads continuity_model.schema.json for validation.
  - `propose_delta(delta: BibleDelta) → ProposedDelta`: validate delta structure against continuity_model.schema.json; return with proposed_id.
  - `validate_delta(delta: ProposedDelta, current_bible: BibleState) → ValidationResult`: check for 6 contradiction types:
    - `type_mismatch`: entity in delta has different type than existing entity with same id.
    - `timeline_violation`: event timestamp conflicts with established timeline.
    - `spatial`: character placed in location that conflicts with known spatial relationship.
    - `capability`: character performs action that contradicts established capability.
    - `voice`: dialogue/behavior violates character's established voice signature.
    - `taboo`: delta introduces content prohibited by sensitivity profile.
  - `commit_delta(delta: ProposedDelta, book_id: str)`: (a) acquire exclusive file lock (`fcntl.flock`); (b) load current bible JSON; (c) apply delta; (d) compute new content hash (SHA-256 of serialized bible + previous hash); (e) write to temp file; (f) `os.replace(temp, bible_path)` (atomic); (g) append event to `bible_events.jsonl`; (h) write snapshot. Release lock in finally block.
  - `query(entity_id: str) → BibleEntity | None`: read current bible JSON; return entity by id.
- T9.2 — Define `BibleDelta`, `ProposedDelta`, `ValidationResult`, `BibleState`, `BibleEntity` typed dataclasses in `pipeline/continuity/bible_types.py`. All validated against `continuity_model.schema.json` at construction.
- T9.3 — Implement `pipeline/continuity/loop_tracker.py`. LoopTracker class:
  - `__init__(promise_ledger, series_promise_ledger)`: takes ledger instances from LedgerManager.
  - `enforce_promise_deadlines(chapter: int) → list[OverduePromise]`: query promise_ledger for all promises with `must_resolve_by < chapter` and `resolution_state == open`. Return list.
  - `check_chapter_can_ship(chapter: int) → bool`: returns False if any overdue promises. Chapter does not ship while overdue promises exist.
  - `enforce_series_threads(book: int) → list[OverdueSeriesPromise]`: query series_promise_ledger for cross-book promises overdue by book.
  - `mark_promise_resolved(promise_id: str, resolution_scene: str)`: update promise_ledger event.
- T9.4 — Port `continuity_agent.py` from `.workspace/manus-agnostic/`. Rewrite as thin wrapper over BibleSteward + LoopTracker. ContinuityAgent: `run(job_context: JobContext) → JobContext`: (a) extract proposed bible deltas from scene output; (b) call `bible_steward.propose_delta` + `validate_delta` for each; (c) if any contradiction → set `job_context.bible_contradiction = True`; (d) else call `commit_delta`; (e) call `loop_tracker.enforce_promise_deadlines(chapter)` and append results.
- T9.5 — Port `series_arc_tracker.py` from manus-agnostic. Extend: `update(series_arc_event: SeriesArcEvent)` writes to `SeriesPromiseLedger` via LedgerManager. Failure is fatal: no `try/except` wrapping in caller code — series arc update failure propagates up and stops the scene pipeline. (MBSE policy: `publishing.require_series_arc_update: true`.)
- T9.6 — Integrate with ConvergenceController in `pipeline/convergence_controller.py`: add two new routing checks before existing logic: (1) `if job_context.bible_contradiction: return ConvergenceDecision.RE_PLAN`. (2) `if job_context.overdue_promises and revise_count < max_revisions: return ConvergenceDecision.REVISE`. These checks run before quality-gate checks.
- T9.7 — Wire BibleSteward + LoopTracker into the scene state machine: add `continuity_node` in LangGraph graph between quality_node and the convergence decision branch. ContinuityAgent runs after QualityAgent approves.
- T9.8 — Write unit tests `tests/unit/continuity/test_bible_steward.py`: (1) Contradiction test (type_mismatch: commit delta that changes character from protagonist to antagonist after established as protagonist → rejected). (2) Timeline violation test. (3) Atomic commit test (verify no partial write by reading bible before and after a simulated interrupt). (4) Hash chain test (verify event N's hash includes event N-1's hash).
- T9.9 — Write unit tests `tests/unit/continuity/test_loop_tracker.py`: (1) Overdue promise test (chapter 15 with overdue promise from chapter 12 → returns OverduePromise list). (2) Chapter can ship test (no overdue → returns True). (3) Series thread overdue test.
- T9.10 — Write integration test `tests/integration/test_bible_continuity.py`: run 2 scenes end-to-end; first scene commits a character fact to bible; second scene's delta contradicts it → contradiction detected before commit; ConvergenceController routes to RE-PLAN.
- T9.11 — Commit: `feat(continuity): BibleSteward, LoopTracker, ContinuityAgent, SeriesArcTracker — bible + continuity layer (task-009)`.

## Key decisions that affect this task

- **Bible contradiction → RE-PLAN (MBSE B8 fix):** BibleSteward contradiction does not get FORCE-RESOLVED. The Convergence Controller routes to RE-PLAN, which re-plans the scene spec from scratch.
- **Overdue promise → REVISE then RE-PLAN:** LoopTracker overdue promise is softer than a bible contradiction — it allows REVISE attempts. But it cannot be ignored or FORCE-RESOLVED without a log entry.
- **Series arc update failure is fatal (MBSE policy):** No exception handling around `series_arc_tracker.update()` in the pipeline. If it fails, the scene pipeline fails.
- **Atomic commits (DEC-006 / Reproducibility):** BibleSteward uses `os.replace()` + exclusive lock + content-hash chain. Crash during commit does not corrupt the bible.
- **Append-only event log (DEC-006):** `bible_events.jsonl` is append-only. Historical bible state is always recoverable from the event log.

## Suggested approach

1. Define all typed dataclasses in `bible_types.py` first.
2. Implement BibleSteward — start with `propose_delta` + `validate_delta`; test contradiction detection before writing `commit_delta`.
3. Implement the atomic `commit_delta` — test the hash chain and atomic write.
4. Implement LoopTracker.
5. Port ContinuityAgent + SeriesArcTracker.
6. Integrate into ConvergenceController (add two new routing checks).
7. Wire into scene state machine (add continuity_node).
8. Write all tests.
9. Run integration test.
10. Commit.

## Decisions to log in DECISIONS.md

- File lock implementation (fcntl.flock on Linux; note platform limitation).
- Content-hash chain algorithm (SHA-256 of serialized JSON + previous hash).
- Snapshot frequency (per-commit vs per-chapter — recommend: per-commit for V1; switch to per-chapter if I/O becomes bottleneck).
- Series arc update fatality: no exception wrapping (log this as an explicit safety decision).

## Notes

- Manus-agnostic source files: `.workspace/manus-agnostic/continuity_agent.py`, `series_arc_tracker.py`.
- The BibleSteward is the most safety-critical component in the pipeline. A corrupted bible corrupts the entire manuscript. The atomic write + hash chain is non-negotiable.
- The 6 contradiction types in `validate_delta` require reading the existing bible state. Implement `query()` before `validate_delta`.
- The `voice` contradiction type (character behavior violates established voice signature) may require a light LLM call or a rule-based heuristic. Start with rule-based (forbidden_phrases from character voice_signature) for V1.

## Out of scope

- Book-level structural verification (Phase 10)
- Cross-book arc planning (Phase 10 — SeriesArcTracker writes to the ledger; planning is Phase 10)
- Paperclip/WUPHF bible sync (Phase 11 — WUPHF wiki gets the bible via git sync)
