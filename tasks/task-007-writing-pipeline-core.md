# Task 007 — Writing Pipeline Core

```
status: pending
started:
completed:
phase: 7
estimated_hours: 12-18
depends_on: task-006
```

## Goal

End-to-end scene generation: spec → WriterAgent → EditorAgent → QualityAgent → Convergence Controller → FINAL. Scene lifecycle managed by LangGraph state machine with SQLite checkpointing. First smoke test milestone: one scene end-to-end with test-tier models in under 90 seconds.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 7 (Writing Pipeline Core)

## Dependencies

- task-006 (agent foundation — AgentContext, ModelRouter+Instructor, BaseAgent, JobContext, ProjectLayout)
- task-003 (LedgerManager — updated after each finalized scene)
- task-002 (convergence.schema.json — Convergence Controller decision rules)

## Acceptance criteria

- [ ] `pipeline/agents/writer_agent.py` — WriterAgent ported from manus-agnostic; uses AgentContext + Instructor + ContextPack; `impl_class = "llm"`
- [ ] `pipeline/agents/editor_agent.py` — EditorAgent ported; integrates with VoiceProfile forbidden_constructions; `impl_class = "llm"`
- [ ] `pipeline/agents/scanner.py` — NoFlyScanner ported; deterministic; `impl_class = "deterministic"`
- [ ] `pipeline/agents/structural_analysis.py` — StructuralAnalyzer ported; deterministic; `impl_class = "deterministic"`
- [ ] `pipeline/agents/quality_agent.py` — QualityAgent ported; uses QualityEvaluator from Phase 3 (running-total contribution scoring); updates all 10 ledgers after finalized scene; fail-closed on evaluator exception
- [ ] `pipeline/convergence_controller.py` — implements GO / REVISE / RE-PLAN / FORCE-RESOLVE; Sensitivity violations → RE-PLAN (cannot FORCE-RESOLVE); budget exhausted → FORCE-RESOLVE with log entry; never halts
- [ ] `pipeline/scene_state_machine.py` — LangGraph graph: 6 states (Unspecced, Specced, DirtyDraft, NeedsReview, Approved, Final); edges with guard conditions; SQLite checkpointing (pause/resume)
- [ ] `pipeline/job_runner.py` — integrates with LangGraph state machine; model tier from AgentContext
- [ ] `pipeline/spec_loader.py` — validates all loaded specs against JSON Schema; no sentinel strings survive validation (`"REQUIRED — fill in"` → schema validation error)
- [ ] **SMOKE TEST MILESTONE (T7.9):** one scene end-to-end with test-tier models against fixture series spec; must complete in under 90 seconds
- [ ] Smoke test verifies: (a) parse scene spec, (b) call WriterAgent via Haiku, (c) call EditorAgent, (d) call QualityAgent, (e) produce FINAL output without errors, (f) update all 10 ledgers, (g) complete in < 90s
- [ ] No API key present → fail-closed with clear error (never silent pass through)
- [ ] Convergence Controller test: REVISE routing on quality gate failure
- [ ] Convergence Controller test: RE-PLAN routing on Sensitivity violation (not FORCE-RESOLVE)
- [ ] Convergence Controller test: FORCE-RESOLVE routing on budget exhaustion + log entry
- [ ] LangGraph state machine: all 6 state transitions pass with fixture inputs
- [ ] LedgerManager updates after FINAL scene (all 10 ledgers receive event)
- [ ] `make test` passes

## Subtasks

- T7.1 — Port `writer_agent.py` from `.workspace/manus-agnostic/`. Adaptations: (1) Constructor takes `AgentContext` (not individual params). (2) `run(job_context: JobContext) → JobContext`: builds ContextPack via `ContextPackBuilder`; calls ModelRouter with Instructor; returns typed `WriterOutput` pydantic model appended to JobContext. (3) `impl_class = "llm"`. (4) All path access via `ProjectLayout`. Log call to cost_log.jsonl.
- T7.2 — Port `editor_agent.py` from manus-agnostic. Adaptations: (1) AgentContext injection. (2) VoiceProfile forbidden_constructions: run regex scan on draft text before submitting to LLM; flag matches in EditorInput. (3) Instructor wrapping on all LLM calls. (4) Returns typed `EditorOutput`.
- T7.3 — Port `scanner.py` (NoFlyScanner) and `structural_analysis.py` from manus-agnostic. Both are deterministic: no Instructor needed. Adapt constructor to take AgentContext. NoFlyScanner: scan draft text against `ai_tell_catalog.schema.json` patterns loaded from registry; count by severity. StructuralAnalyzer: compute word count, sentence length avg, interiority_pct, dialogue_ratio, exposition_pct, action_pct from draft text.
- T7.4 — Port `quality_agent.py` from manus-agnostic. Extensions: (1) Call `QualityEvaluator.evaluate_scene_contribution(scene_metrics, running_totals, targets, word_count_remaining)` — not a per-scene threshold check. (2) After FINAL decision: call `ledger_manager.update(scene_result)` to update all 10 ledgers. (3) Fail-closed: any QualityEvaluator exception → routing_decision = `needs_review`, log exception, never silent pass. (MBSE B11/B12 fix.)
- T7.5 — Implement `pipeline/convergence_controller.py`. Load decision rules from `schemas/universal/convergence.schema.json`. `decide(quality_result: QualityResult, job_context: JobContext) → ConvergenceDecision` (enum: GO/REVISE/RE-PLAN/FORCE-RESOLVE). Rules: (1) Sensitivity violation → RE-PLAN (hard-coded check, not just schema rule). (2) quality_result.needs_review AND revise_count < max_revise_attempts → REVISE. (3) quality_result.needs_review AND revise_count >= max_revisions → RE-PLAN. (4) Budget exhausted (word_count_remaining ≤ 0) → FORCE-RESOLVE with mandatory log entry to DECISIONS.md. (5) All gates passed → GO. Never returns a halt/wait action. Log every FORCE-RESOLVE to decisions ledger.
- T7.6 — Implement `pipeline/scene_state_machine.py`. LangGraph `StateGraph`: nodes = {specced_node, writer_node, editor_node, quality_node, force_resolve_node, final_node}. Edges: specced → writer → editor → quality → [convergence decision branch: GO→final, REVISE→writer, RE-PLAN→specced, FORCE-RESOLVE→force_resolve→final]. Guards: check state validity at each edge. SQLite checkpoint store: `langgraph.checkpoint.sqlite.SqliteSaver`. `pause_at` marks: after NeedsReview (for future human-review mode, currently unused). State = `SceneState` typed dataclass (current_state, job_context, revise_count, convergence_history).
- T7.7 — Implement `pipeline/job_runner.py`. Port from manus-agnostic. Integrate with `scene_state_machine.py`: compile graph, invoke with initial SceneState. Model tier from `job_context.model_tier` (read from AgentContext). `run_scene(job_context: JobContext) → SceneResult`. `resume(checkpoint_id: str) → SceneResult`.
- T7.8 — Implement `pipeline/spec_loader.py` (if not already from Phase 4 SpecLoader). Add: validate all loaded specs against their JSON schemas (`jsonschema.validate`). Sentinel check: if any string field value equals `"REQUIRED — fill in"` → raise `SentinelStringError`. (MBSE B4/B5 / M2 fix.)
- T7.9 — **SMOKE TEST (MILESTONE):** Write `tests/integration/test_smoke_pipeline.py::test_one_scene_end_to_end`. Fixture: `tests/fixtures/pipeline/fixture_series_spec.yaml` + `tests/fixtures/pipeline/fixture_scene_spec.yaml`. Test: (a) load fixture specs via spec_loader (no sentinel strings), (b) build AgentContext with test-tier ModelRouter, (c) run scene via job_runner, (d) assert FINAL state reached, (e) assert all 10 ledger updates occurred, (f) assert elapsed_seconds < 90. API key required: if ANTHROPIC_API_KEY not set, skip test with `pytest.mark.skipif` and clear message (fail-closed, never silent). Run with: `pytest tests/integration/test_smoke_pipeline.py -v --timeout=120`.
- T7.10 — Write fixture files: `tests/fixtures/pipeline/fixture_series_spec.yaml` (minimal valid series spec: 1 book, 1 chapter, 1 scene, Romance module v1, test-tier models) and `tests/fixtures/pipeline/fixture_scene_spec.yaml` (scene 1.1: 1200 words target, meet_cute function, heat_level 1).
- T7.11 — Write convergence controller unit tests `tests/unit/test_convergence_controller.py`: GO test, REVISE test, RE-PLAN-on-sensitivity test (assert action == RE-PLAN not FORCE-RESOLVE), FORCE-RESOLVE-on-budget-exhaustion test (assert log entry written).
- T7.12 — Write state machine tests `tests/unit/test_scene_state_machine.py`: all 6 state transitions with mock agents; checkpoint save + restore test.
- T7.13 — Commit: `feat(pipeline): writing pipeline core — WriterAgent, EditorAgent, QualityAgent, ConvergenceController, LangGraph scene state machine (task-007)`. Note smoke test milestone in commit message body.

## Key decisions that affect this task

- **Every Claude call through Instructor (decisions.md 2026-05-15):** WriterAgent and EditorAgent calls return pydantic models. No raw text response handling.
- **Sensitivity violations → RE-PLAN only (DEC-005):** ConvergenceController has a hard-coded check for sensitivity_violation == True → RE-PLAN. This check runs before all other routing logic.
- **QualityEvaluator fail-closed (DEC-008):** Any exception → `needs_review`. Never silent pass. This is the most critical safety property in the pipeline.
- **Running-total contribution scoring (DEC-010):** QualityAgent calls QualityEvaluator with running totals from LedgerManager, not per-scene absolute metrics.
- **LangGraph as primary state machine (decisions.md 2026-05-15):** LangGraph manages scene lifecycle (Unspecced → Final). ROMA drives planning phase (Phase 11). Do not conflate them.
- **Sentinel string rejection (MBSE B4/B5):** `spec_loader.py` rejects any spec with a field value of "REQUIRED — fill in". Hard error, not warning.
- **Model tiering (DEC-009):** Smoke test uses test tier. Never promote to production tier before Phase 14.

## Suggested approach

1. Port the 4 agents (writer, editor, scanner, structural_analysis) first — adapt to AgentContext pattern.
2. Port quality_agent — extend with QualityEvaluator integration and fail-closed contract.
3. Implement convergence_controller — write unit tests first.
4. Implement scene_state_machine — wire all nodes; test transitions with mock agents.
5. Implement job_runner — thin orchestrator over state machine.
6. Extend spec_loader with sentinel check.
7. Write smoke test fixture specs.
8. Run smoke test: `pytest tests/integration/test_smoke_pipeline.py -v --timeout=120`. Iterate until it passes.
9. Commit with smoke test milestone noted.

## Decisions to log in DECISIONS.md

- LangGraph version and checkpoint store choice (SQLite for V1 simplicity).
- SceneState as typed dataclass (not raw LangGraph State dict).
- Smoke test timeout (90 seconds for single scene; 120s pytest timeout for buffer).
- Convergence Controller hard-coded sensitivity check (safety over flexibility).

## Notes

- Manus-agnostic source files for reference: `.workspace/manus-agnostic/writer_agent.py`, `editor_agent.py`, `quality_agent.py`, `job_runner.py`, `scanner.py`, `structural_analysis.py`. Read before porting.
- The smoke test is the first milestone where the pipeline is actually running. Invest time here. If the smoke test can't pass, subsequent phases cannot be validated.
- WriterAgent output must be a pydantic model (not raw prose string) at the JobContext level. The prose content is a field within the model.
- NoFlyScanner and StructuralAnalyzer are deterministic — they run regex and heuristics, not LLMs. Keep them fast.
- ConvergenceController never halts. If it runs out of valid routing options, it FORCE-RESOLVES with a log entry. The pipeline always terminates.

## Out of scope

- Specialist agents (Phase 8)
- BibleSteward / LoopTracker integration (Phase 9)
- Book-level orchestration (Phase 10)
- Paperclip / WUPHF integration (Phase 11)
- DeepEval quality metrics (Phase 14)
