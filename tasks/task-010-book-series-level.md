# Task 010 — Book + Series Level

```
status: pending
started:
completed:
phase: 10
estimated_hours: 8-12
depends_on: task-009
```

## Goal

Book-level orchestration: spec-driven scene planning, structural verification, series arc management. Orchestrator becomes the top-level CLI with commands for spec validation, book initialization, scene execution, structural verification, and status reporting. All paths through ProjectLayout; no sentinel strings survive spec loading.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 10 (Book + Series Level)

## Dependencies

- task-009 (BibleSteward, LoopTracker, SeriesArcTracker — orchestrator integrates with all)
- task-007 (job_runner — orchestrator CLI delegates scene execution to it)
- task-004 (SpecLoader — orchestrator uses it for spec validation and loading)
- task-006 (ProjectLayout — all paths through it)

## Acceptance criteria

- [ ] `pipeline/book_structure_planner.py` — reads series + book spec → generates full scene inventory (act/chapter/scene assignments, word targets, heat_level per scene from heat_curve)
- [ ] `pipeline/book_structural_verifier.py` — checks: word count, act proportions, scene count, heat_curve compliance, HEA/HFN (Romance module), sex_scene frequency (Erotica module), all RTM requirements
- [ ] `pipeline/orchestrator.py` — thin CLI; commands: `--validate-spec`, `--init-book`, `--job`, `--resume`, `--verify-book`, `--book-publish`, `--status`
- [ ] `pipeline/spec_validator_agent.py` — thin wrapper over `jsonschema.validate` against Phase 2 canonical schemas; sentinel string check: reject any field equaling `"REQUIRED — fill in"` (MBSE B4/B5)
- [ ] All agents access paths through `ProjectLayout` — no string concatenation anywhere in pipeline code (MBSE B1)
- [ ] Integration test T10.6: `--validate-spec` passes against fixture series spec → `--init-book` generates scene inventory → `--job` for scene 1.1 generates FINAL output → `--verify-book` reports compliance
- [ ] `--validate-spec` correctly rejects spec with a sentinel string field
- [ ] `--verify-book` correctly fails against fixture with missing heat_curve data
- [ ] BookStructuralVerifier: Romance module → checks HEA/HFN present at 0.95–1.0; fails if absent
- [ ] BookStructuralVerifier: Erotica module → checks sex_scene_frequency_min; fails if frequency below threshold
- [ ] `make test` passes

## Subtasks

- T10.1 — Port `book_structure_planner.py` from `.workspace/manus-agnostic/`. BookStructurePlanner: `plan(series_spec: SeriesSpec, book_spec: BookSpec) → SceneInventory`. SceneInventory: list of SceneSlot (scene_id, chapter, act, word_count_target, scene_function, heat_level_target, required_slot_id or None). Heat level per scene: read `heat_curve` from genre_profile and interpolate based on scene's position (scene_index / total_scenes) in book. Log SceneInventory to `{book_id}/scene_inventory.json`.
- T10.2 — Port `book_structural_verifier.py` from manus-agnostic. BookStructuralVerifier: `verify(book_output: BookOutput, spec: ProjectSpec) → VerificationReport`. Checks: (1) total word count within spec tolerance (±10%). (2) Act proportions within genre norm (Romance: act 1 ≈ 25%, act 2 ≈ 50%, act 3 ≈ 25%). (3) Scene count matches inventory. (4) Heat curve compliance: for each chapter, actual avg heat_level vs target from heat_curve (within ±1). (5) HEA/HFN check (Romance module): last chapter contains a required_slot marked HEA_or_HFN. (6) Sex scene frequency (Erotica module): total sex_scene_count / (total_scenes/3) ≥ sex_scene_frequency_min from genre profile. (7) RTM requirements: all required_scene_slots in genre profile are fulfilled (by checking scene function assignments against SceneInventory). VerificationReport: passed bool, failed_checks list with descriptions.
- T10.3 — Implement `pipeline/orchestrator.py`. Thin CLI using `argparse` or `click`. Commands:
  - `--validate-spec <series_spec_path>`: call SpecValidatorAgent; exit 0 if valid, exit 1 with error details if not.
  - `--init-book <series_id> <book_number>`: call BookStructurePlanner; write SceneInventory; output count of planned scenes.
  - `--job <scene_id>`: call job_runner.run_scene() for the given scene_id; print FINAL or error.
  - `--resume <checkpoint_id>`: call job_runner.resume(); continue from LangGraph checkpoint.
  - `--verify-book <book_id>`: call BookStructuralVerifier; print VerificationReport.
  - `--book-publish <book_id>`: run `--verify-book`; if passed, assemble output bundle (manuscript .md + generation report + ledger export); write to `output/{book_id}/`.
  - `--status`: print current run state (active scene, last agent, routing decision, cost vs budget) from LedgerManager and cost_log.
- T10.4 — Implement `pipeline/spec_validator_agent.py`. SpecValidatorAgent: `validate(spec_path: Path) → ValidationResult`. Steps: (1) Load YAML. (2) Validate against series_spec schema (to be authored alongside this task if not yet done). (3) Sentinel check: recursively walk all string field values; any that equal `"REQUIRED — fill in"` → ValidationError with field path. (4) Check required top-level keys. Return ValidationResult with errors list. (MBSE B4/B5 fix.)
- T10.5 — Audit all pipeline code for hand-assembled path strings. Use `grep -rn "os.path.join\|Path.*+.*/" pipeline/`. Any found → replace with ProjectLayout method call. (MBSE B1 fix — verify completed across all phases.)
- T10.6 — Write integration test `tests/integration/test_book_series_level.py::test_full_book_pipeline_integration`: (1) Call `orchestrator --validate-spec` with fixture series spec → assert exit 0. (2) Call `--init-book series_fixture 1` → assert SceneInventory written with > 0 scenes. (3) Call `--job scene_1_1` → assert FINAL state. (4) Call `--verify-book book_fixture_1` → assert VerificationReport.passed == True (or known failures listed). This is the primary Phase 10 gate.
- T10.7 — Write `tests/integration/test_spec_validator.py`: (1) Sentinel string test: spec with `word_count_target: "REQUIRED — fill in"` → rejected with error citing field path. (2) Valid spec → passes. (3) Missing required key → rejected.
- T10.8 — Write `tests/unit/test_book_structural_verifier.py`: (1) Missing HEA/HFN (Romance) → fails with description. (2) Heat curve violation (chapter 3 has heat_level 1 when target is 3) → fails. (3) Sex scene frequency (Erotica) below minimum → fails. (4) Valid fixture book → passes.
- T10.9 — Write `tests/unit/test_book_structure_planner.py`: (1) Fixture series + book spec → SceneInventory with correct scene count. (2) Heat levels interpolated from heat_curve correctly.
- T10.10 — Commit: `feat(orchestration): BookStructurePlanner, BookStructuralVerifier, orchestrator CLI, SpecValidatorAgent (task-010)`.

## Key decisions that affect this task

- **All paths through ProjectLayout (MBSE B1 fix):** Orchestrator and all components use `ProjectLayout` methods. Verify with grep in T10.5.
- **Sentinel string rejection (MBSE B4/B5 / M2 fix):** SpecValidatorAgent raises on `"REQUIRED — fill in"` strings. This is a hard validation failure, not a warning.
- **Heat curve as genre profile data:** BookStructurePlanner reads heat_curve from genre_profile.yaml loaded via SpecLoader. Never hardcodes target heat levels.
- **RTM requirements from genre profile:** BookStructuralVerifier checks required_scene_slots list from genre_profile.yaml. The verification logic is generic; the requirements are data.
- **No human gates in inner loop (DEC-004):** `--book-publish` is a human gate (user runs it). The inner generation loop (job/resume) is fully autonomous.

## Suggested approach

1. Port BookStructurePlanner — test heat_curve interpolation with Romance module fixture.
2. Port BookStructuralVerifier — write unit tests before implementing each check.
3. Implement SpecValidatorAgent — sentinel check first (simplest).
4. Implement orchestrator CLI — start with `--validate-spec` and `--status`; add others in order.
5. Audit for path string concatenation (T10.5).
6. Write integration test T10.6 — this is the phase gate.
7. Run `make test`; verify all pass.
8. Commit.

## Decisions to log in DECISIONS.md

- CLI framework choice (argparse vs click — recommend: click for subcommands, but argparse for zero-dependency baseline).
- SceneInventory storage format (JSON at book_id/scene_inventory.json).
- `--book-publish` output bundle format (manuscript .md + generation report + ledger export as zip).
- RTM verification scope for V1 (required_scene_slots only; RTM traceability matrix from MBSE is V2).

## Notes

- Manus-agnostic source files: `.workspace/manus-agnostic/orchestrator.py`, `book_structure_planner.py`, `book_structural_verifier.py`. Read before porting.
- The integration test T10.6 is the Phase 10 gate. It exercises the full pipeline from spec validation through scene generation through structural verification. If T10.6 passes, Phase 10 is complete.
- BookStructuralVerifier reports failures — it does not halt the pipeline. The user reviews the report via `--verify-book` before calling `--book-publish`. This is one of the two human gates.
- Series-level planning (ROMA decomposition) is Phase 11. This task handles book-level planning only.

## Out of scope

- ROMA recursive decomposition for series planning (Phase 11)
- Paperclip/WUPHF integration (Phase 11)
- Author Dashboard (Phase 13)
- DeepEval CI gates (Phase 14)
