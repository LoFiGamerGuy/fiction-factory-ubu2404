# Task 004 — Profile System

```
status: pending
started:
completed:
phase: 4
estimated_hours: 6-10
depends_on: task-002
```

## Goal

All 5 primary profile schemas authored and validated. ProfileRegistry loads and composes profiles into a `ProjectSpec` via `SpecLoader`. ConflictResolver enforces Constraint > Sensitivity > Goal > Genre > Audience > Author > Universal precedence. Sensitivity thresholds are sacred and cannot be overridden by Goal.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 4 (Profile System)

## Dependencies

- task-002 (universal core schemas — voice_axes.schema.json used as base; pydantic models available)

## Acceptance criteria

- [ ] `schemas/profiles/author_profile.schema.json` — all 9 voice axis categories from Bunko schema; validates against meta-schema
- [ ] `schemas/profiles/genre_profile.schema.json` — scene_function_vocabulary, required_scene_slots, quality_gates, self_audit_rubric, heat_scale, structural_conventions, trope_library, reader_contract; validates
- [ ] `schemas/profiles/audience_profile.schema.json` — reader lens, tolerance bands, expectation set, trigger sets, reader personas (3–5 named); validates
- [ ] `schemas/profiles/sensitivity_profile.schema.json` — content domain policies, vocabulary restrictions, audience markers, hard thresholds marked sacred; validates
- [ ] `schemas/profiles/goal_profile.schema.json` — intent enum, conflict precedence rules, weight overrides, success criteria; validates
- [ ] `make validate-schemas` covers all profile schemas and passes clean
- [ ] Pydantic models generated for all 5 profile schemas into `pipeline/schemas/profiles/`
- [ ] `pipeline/profiles/profile_registry.py` — ProfileRegistry: loads profiles by type + name from `profiles/` YAML files; validates each against its schema; composes them into a `ProjectSpec` via `SpecLoader`
- [ ] `pipeline/profiles/spec_loader.py` — SpecLoader: overlay architecture; apply conflict precedence; produce `ProjectSpec` (typed dataclass); pin profile version at load time
- [ ] `pipeline/profiles/conflict_resolver.py` — ConflictResolver: implements 7-level precedence (Constraint > Sensitivity > Goal > Genre > Audience > Author > Universal); per-field overrides; logs all conflicts resolved to DECISIONS.md
- [ ] Test: compose ProjectSpec from fixture profiles — all 5 types, valid result
- [ ] Test: all 6 precedence levels fire correctly with fixture conflicts
- [ ] Test: Sensitivity sacred threshold — Goal profile cannot loosen Sensitivity max_heat; assertion that resolved spec has Sensitivity's max_heat, not Goal's requested loosening
- [ ] Test: round-trip load → compose → serialize → validate
- [ ] `make test` passes

## Subtasks

- T4.1 — Author `schemas/profiles/author_profile.schema.json`. Fields: profile_id, version, display_name, voice_axes (object referencing voice_axes.schema.json field categories: sentence_level, lexical, syntactic, dialogue, sensory, pacing, metaphor, subtext, cadence), forbidden_constructions (list of regex strings), enforcement_weights (dict: axis_name → float 0–1), calibration_history (list of calibration run references).
- T4.2 — Author `schemas/profiles/genre_profile.schema.json`. Fields: profile_id, version, genre_name, genre_module_status (enum: validated/scaffold/experimental), scene_function_vocabulary (list of strings), required_scene_slots (list of: slot_id, description, target_chapter_range min/max, required bool), quality_gates (list of gate_id + metric + threshold + operator), self_audit_rubric (list of rubric items), heat_scale (object: min 1 / max 5 / anchor_definitions dict), structural_conventions (object: word_count_range min/max, chapter_count_range, act_structure), trope_library (list of trope_id + name + required_beats list), reader_contract (list of promise type strings that must resolve).
- T4.3 — Author `schemas/profiles/audience_profile.schema.json`. Fields: profile_id, version, reader_lens (string description), tolerance_bands (dict: dimension → min/max), expectation_set (list of expectation strings), trigger_sets (object: dnf_triggers list, satisfaction_triggers list), reader_personas (list of: persona_id, name, description, reading_preferences dict).
- T4.4 — Author `schemas/profiles/sensitivity_profile.schema.json`. Fields: profile_id, version, content_domain_policies (dict: domain → policy: allow/allow_with_constraints/prohibit), vocabulary_restrictions (list of: term or regex, restriction_level: prohibited/flagged), audience_markers (list of applicable audience labels), hard_thresholds (dict: threshold_name → value), sacred (boolean, always true — marks that Goal cannot loosen this profile). Add `x-sacred: true` annotation on hard_thresholds to document the constraint.
- T4.5 — Author `schemas/profiles/goal_profile.schema.json`. Fields: profile_id, version, intent (enum: kdp_high_revenue/literary_award_target/personal_vanity/series_brand), conflict_precedence_rules (list of: axis, precedence_order list of profile types), weight_overrides (object: critic_weights dict + reader_weights dict), success_criteria (list of: criterion_id, metric, threshold, operator).
- T4.6 — Update `scripts/validate_schemas.py` to include `schemas/profiles/*.schema.json`. Run `make validate-schemas`.
- T4.7 — Generate pydantic models: `datamodel-codegen --input schemas/profiles/ --output pipeline/schemas/profiles/ --input-file-type jsonschema --output-model-type pydantic_v2.BaseModel`.
- T4.8 — Implement `pipeline/profiles/spec_loader.py`. SpecLoader: `load(profile_type: str, name: str) → BaseProfile` loads YAML from `profiles/{type}/{name}.yaml`, validates against schema, returns typed pydantic model with version pinned. `get_series_spec_path(series_id: str) → Path`. `get_book_spec_path(series_id: str, book_id: str) → Path`.
- T4.9 — Implement `pipeline/profiles/conflict_resolver.py`. ConflictResolver: `resolve(author, genre, audience, sensitivity, goal) → ProjectSpec`. For each conflicting field: apply 7-level precedence. Sacred sensitivity check: if goal requests loosening a Sensitivity hard_threshold, raise `SensitivityViolation` (never silently override). Log all resolved conflicts to DECISIONS.md via structured append.
- T4.10 — Implement `pipeline/profiles/profile_registry.py`. ProfileRegistry: holds SpecLoader + ConflictResolver. `compose(author_name, genre_name, audience_name, sensitivity_name, goal_name) → ProjectSpec`. Validates all 5 profiles before composing. Returns immutable ProjectSpec with pinned versions.
- T4.11 — Define `ProjectSpec` typed dataclass in `pipeline/profiles/project_spec.py`: resolved voice_axes, resolved genre config, resolved sensitivity thresholds, resolved goal weights, resolved audience expectations, profile_versions dict, composition_timestamp, is_frozen bool.
- T4.12 — Write test fixtures: `tests/fixtures/profiles/fixture_{author,genre,audience,sensitivity,goal}.yaml` — minimal but valid YAML for each schema.
- T4.13 — Write tests `tests/unit/profiles/test_profile_system.py`: fixture composition (5 profiles → valid ProjectSpec), all 6 precedence conflict tests, sacred sensitivity test (Goal cannot loosen max_heat), round-trip test, SensitivityViolation test.
- T4.14 — Commit: `feat(profiles): profile schemas, ProfileRegistry, ConflictResolver, SpecLoader (task-004)`.

## Key decisions that affect this task

- **Conflict precedence (DEC-001):** Constraint > Sensitivity > Goal > Genre > Audience > Author > Universal. Encoded in ConflictResolver, not in any profile file.
- **Sensitivity thresholds are sacred (DEC-005):** `SensitivityViolation` is raised — not a soft warning. Goal cannot loosen Sensitivity even via precedence rules.
- **Schemas are the contract (DEC-007):** YAML profile files validate against the 5 profile schemas before composing. No bare dict access.
- **Reproducibility (DEC-006):** Profile versions pinned in ProjectSpec at load time. Same profile version + same inputs = same ProjectSpec.
- **Heavier-weight from start (DEC-008):** ProfileRegistry validates all 5 profiles before composing. No lazy validation.

## Suggested approach

1. Author author_profile.schema.json first (builds on voice_axes from Phase 2).
2. Author the remaining 4 schemas.
3. Run `make validate-schemas` after each.
4. Generate pydantic models.
5. Implement SpecLoader (simple loading + validation).
6. Implement ConflictResolver (the complex logic — write tests before implementing).
7. Implement ProfileRegistry (thin orchestrator over the two above).
8. Write tests; verify sacred threshold test passes.
9. Commit.

## Decisions to log in DECISIONS.md

- YAML for human-edited profiles (vs TOML or JSON).
- ProjectSpec as frozen dataclass (immutable after composition).
- SensitivityViolation as raised exception (not log warning).
- Conflict logging format (structured append to DECISIONS.md vs separate conflict_log.jsonl — recommend: DECISIONS.md for auditability).

## Notes

- Profile data files are NOT authored in this task — that is Phase 5. This task delivers the schemas, code machinery, and fixture YAML only.
- The conflict_resolver.py is the most complex piece. Write the tests first, then implement.
- ConflictResolver logging to DECISIONS.md must not overwrite — append-only.
- SpecLoader's `get_series_spec_path` and `get_book_spec_path` are used by SpecValidatorAgent in Phase 10 (MBSE B1 fix).

## Out of scope

- Real profile data files (Phase 5 — `profiles/`)
- SpecValidatorAgent (Phase 10)
- Agent integration (Phase 6)
- Dashboard display of profiles (Phase 13)
