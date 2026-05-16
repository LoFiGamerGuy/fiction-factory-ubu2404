# Task 003 — Ledger System

```
status: pending
started:
completed:
phase: 3
estimated_hours: 8-12
depends_on: task-002
```

## Goal

All 10 ledgers implemented as append-only SQLite event logs with JSON schemas, Python classes, a `LedgerManager` that aggregates them, `get_dashboard_summary()` for context-pack injection, and a `QualityEvaluator` that scores scene contribution to running totals — not per-scene absolute values.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 3 (Ledger System)

## Dependencies

- task-002 (universal core schemas — PromiseLedger schema must exist before this task extends the ledger pattern)

## Acceptance criteria

- [ ] `schemas/ledgers/book_metrics_ledger.schema.json` — event schema for each finalized scene (all fields per T3.1); validates against meta-schema
- [ ] `schemas/ledgers/character_arc_ledger.schema.json` — per-character arc event; validates
- [ ] `schemas/ledgers/intimacy_escalation_ledger.schema.json` — per character pair events; validates
- [ ] `schemas/ledgers/reader_information_state.schema.json` — revelation events; validates
- [ ] `schemas/ledgers/subplot_ledger.schema.json` — subplot events; validates
- [ ] `schemas/ledgers/trope_commitment_ledger.schema.json` — trope activation + required beats; validates
- [ ] `schemas/ledgers/series_promise_ledger.schema.json` — cross-book promise events; validates
- [ ] `make validate-schemas` covers all ledger schemas and passes clean
- [ ] `pipeline/ledgers/book_metrics_ledger.py` — SQLite-backed append-only log with `compute_running_totals()` and `budget_remaining(target, word_count_remaining)`
- [ ] 9 additional ledger classes following the same SQLite-backed pattern (character_arc, intimacy_escalation, reader_information_state, subplot, trope_commitment, series_promise, scene_rhythm, promise_ledger wrapper, bible_tracker wrapper)
- [ ] `pipeline/ledgers/ledger_manager.py` — `LedgerManager.update(scene_result)` updates all 10 ledgers; `get_dashboard_summary(book_id, scene_id) → AuthorDashboard` returns structured summary with all 10 ledger states
- [ ] `pipeline/ledgers/quality_evaluator.py` — `QualityEvaluator.evaluate_scene_contribution(scene_metrics, running_totals, targets, word_count_remaining)` evaluates contribution to running total, not local absolute
- [ ] Quality evaluator test: high-interiority scene passes when running total is below interiority target
- [ ] Quality evaluator test: high-interiority scene fails when running total is already at or above target
- [ ] LedgerManager fixture test: after fixture scene update, `get_dashboard_summary()` returns structured object with all 10 ledger states populated
- [ ] All ledger classes enforce append-only: no UPDATE/DELETE SQL allowed; verify with test
- [ ] `make test` passes

## Subtasks

- T3.1 — Author `schemas/ledgers/book_metrics_ledger.schema.json`. BookMetricsEvent: event_id, book_id, chapter_id, scene_id, finalized_at (ISO timestamp), interiority_pct (0–1), sensory_density_per_1k (number), em_dash_density (number), dialogue_ratio (0–1), heat_curve_position (number 0–1), ai_tell_count (integer ≥ 0), no_fly_violations (integer ≥ 0), sex_scene_flag (boolean), sex_scene_count_running (integer ≥ 0), sentence_length_avg (number), exposition_pct (0–1), action_pct (0–1), word_count (integer > 0).
- T3.2 — Author `schemas/ledgers/character_arc_ledger.schema.json`. CharacterArcEvent: event_id, book_id, chapter_id, scene_id, character_id, arc_position (enum: opening/wound_open/processing/wound_healing/resolved), wound_state (string), core_belief_current (string), core_belief_true (string), relationship_states (object: char_id → status string), timestamp.
- T3.3 — Author `schemas/ledgers/intimacy_escalation_ledger.schema.json`. IntimacyEvent: event_id, book_id, pair_id, chapter_id, scene_id, act_type (enum: first_touch/first_charged_moment/first_kiss/first_explicit/escalation_peak/other), heat_level (integer 1–5), notes (string), timestamp. Ledger document: pair_id, character_ids (list of 2), events (list of IntimacyEvent).
- T3.4 — Author `schemas/ledgers/reader_information_state.schema.json`. RevelationEvent: event_id, book_id, chapter_id, scene_id, fact_id, fact_description, revealed_at_chapter (integer), revealed_at_scene (string), known_by_reader (boolean), known_by_characters (list of char_id strings), irony_type (enum: dramatic/tragic/situational/none), notes, timestamp.
- T3.5 — Author `schemas/ledgers/subplot_ledger.schema.json`. SubplotEvent: event_id, book_id, subplot_id, chapter_id, scene_id, subplot_type (enum: romantic/professional/family/external/thematic), opened_at_chapter (integer), target_resolution_chapter (integer), status (enum: open/escalating/complicating/resolved/abandoned), resolution_scene (nullable string), notes, timestamp.
- T3.6 — Author `schemas/ledgers/trope_commitment_ledger.schema.json`. TropeActivation: trope_id, genre_module, activated_at_chapter (integer), activated_at_scene (string), required_beats (list of: beat_id, description, target_chapter integer, status enum: pending/fulfilled/overdue). TropeEvent: event_id, book_id, trope_activation (TropeActivation), timestamp.
- T3.7 — Author `schemas/ledgers/series_promise_ledger.schema.json`. SeriesPromiseEvent: event_id, series_id, promise_id, promise_type (same enum as universal promise_ledger), description, opened_book (integer), opened_chapter (integer), must_resolve_by_book (integer), resolution_status (enum: open/partially_resolved/resolved/overdue/force_resolved), resolution_book (nullable integer), timestamp.
- T3.8 — Implement `pipeline/ledgers/book_metrics_ledger.py`. BookMetricsLedger: SQLite connection at `data/{book_id}/book_metrics.db`. Schema: CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, payload TEXT NOT NULL, appended_at TEXT NOT NULL). `append(event: BookMetricsEvent)` inserts row; raises if event_id already exists (idempotency guard). `compute_running_totals() → dict[str, float]`: weighted average/sum of all events for cumulative metrics. `budget_remaining(targets: dict, word_count_remaining: int) → dict[str, float]`: difference between target and running total scaled by remaining budget.
- T3.9 — Implement `pipeline/ledgers/character_arc_ledger.py` following same SQLite-backed pattern as BookMetricsLedger. `get_arc_position(character_id: str) → ArcPosition`: returns last event's arc_position for that character.
- T3.10 — Implement `pipeline/ledgers/intimacy_escalation_ledger.py`. `get_pair_history(pair_id: str) → list[IntimacyEvent]`: events for a pair in order. `last_act_type(pair_id: str) → str | None`. `validate_escalation(pair_id: str, proposed_act: str) → bool`: returns False if proposed act is not an escalation from last recorded act.
- T3.11 — Implement remaining 6 ledger classes: `reader_information_state_ledger.py`, `subplot_ledger.py`, `trope_commitment_ledger.py`, `series_promise_ledger.py`. Scene Rhythm Ledger: maintained as an in-memory rolling list (last 10 scene types) within LedgerManager state — no SQLite needed. PromiseLedger and BibleTracker: thin wrappers that bridge the Phase 2 universal schemas into the ledger pattern.
- T3.12 — Implement `pipeline/ledgers/ledger_manager.py`. LedgerManager init: opens/creates all 10 ledger instances for a given book_id. `update(scene_result: SceneResult)`: dispatches scene data to each ledger's `append()`. `get_dashboard_summary(book_id: str, scene_id: str) → AuthorDashboard`: collects running state from all 10 ledgers and returns typed AuthorDashboard dataclass. AuthorDashboard fields: book_metrics_running, character_arcs (dict: char_id → arc_position), intimacy_pairs (dict: pair_id → last_act_type), reader_info_state (count known/unknown facts), subplot_summary (open/resolved counts), trope_commitments (pending/overdue beats), series_promises (open cross-book arcs), scene_rhythm (last 10 scene types), promise_summary (open/overdue promises).
- T3.13 — Implement `pipeline/ledgers/quality_evaluator.py`. QualityEvaluator: `evaluate_scene_contribution(scene_metrics: dict, running_totals: dict, targets: dict, word_count_remaining: int) → QualityDecision`. Logic: for each tracked metric, compute what the running total would be if this scene is accepted. If new running total moves toward or maintains target trajectory, contribution is positive. Fail-closed: any evaluator exception → `needs_review`, never silent pass.
- T3.14 — Write tests `tests/unit/ledgers/test_ledger_system.py`: append-only enforcement test (second INSERT of same event_id raises), running total test, budget_remaining calculation test, quality evaluator contribution tests (high-interiority passes when below target, fails when at/above target), LedgerManager fixture test (fixture scene_result updates all 10 ledgers; dashboard summary has all 10 states).
- T3.15 — Write fixture: `tests/fixtures/ledgers/fixture_scene_result.json` with plausible finalized scene data (word_count 1200, interiority_pct 0.35, dialogue_ratio 0.40, heat_level 2, etc.).
- T3.16 — Update `scripts/validate_schemas.py` to also validate `schemas/ledgers/*.schema.json`. Verify `make validate-schemas` passes.
- T3.17 — Commit: `feat(ledgers): all 10 ledgers, LedgerManager, QualityEvaluator (task-003)`.

## Key decisions that affect this task

- **BookMetricsLedger — running cumulative tracking (DEC-010):** QualityAgent evaluates scene's contribution to running total, not local absolute value. This is encoded in `QualityEvaluator.evaluate_scene_contribution()` — not in any per-scene threshold check.
- **Full ledger inventory (decisions.md 2026-05-15):** All 10 ledgers are V1. Character Arc Ledger and Intimacy Escalation Ledger are V1 priority. Subplot, Trope Commitment, and Series Promise Ledgers are also V1.
- **Append-only logs:** No UPDATE or DELETE SQL anywhere in any ledger class. Idempotency via event_id uniqueness guard.
- **Fail-closed quality evaluation (DEC-008):** QualityEvaluator exception → `needs_review`, never silent pass.
- **Scene Rhythm Ledger:** Rolling window of last 10 scene types maintained in LedgerManager in-memory state. No separate SQLite table needed.

## Suggested approach

1. Author all 7 ledger schemas first; run `make validate-schemas` after each.
2. Implement BookMetricsLedger (most complex — establishes the pattern).
3. Implement remaining 9 ledger classes following the same pattern.
4. Implement LedgerManager (depends on all 10 classes).
5. Implement QualityEvaluator.
6. Write tests using the fixture scene result.
7. Verify `make test` and `make validate-schemas` pass.
8. Commit.

## Decisions to log in DECISIONS.md

- SQLite append-only enforcement approach (event_id PRIMARY KEY + no UPDATE/DELETE).
- Scene Rhythm Ledger as in-memory rolling window (not SQLite — simpler, sufficient).
- AuthorDashboard as a typed dataclass (not raw dict).
- QualityEvaluator fail-closed contract.

## Notes

- The LedgerManager is injected into every agent's AgentContext in Phase 6. Design its interface with that injection in mind.
- `get_dashboard_summary()` output is injected into every scene's context pack. Keep it compact — it must fit within context budget.
- The intimacy escalation ledger directly addresses the erotica/pacing concern: the system can detect "first kiss" duplication or stalled escalation at any scene.
- Do not implement QualityAgent here — that is Phase 7. This task delivers the evaluation engine the agent will call.

## Out of scope

- QualityAgent (Phase 7)
- LedgerManager integration with agents (Phase 6)
- Author Dashboard API endpoints (Phase 13)
- LangGraph checkpoint integration (Phase 14)
