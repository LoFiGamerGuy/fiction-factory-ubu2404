# Task 002 — Universal Core Schemas

```
status: pending
started:
completed:
phase: 2
estimated_hours: 6-10
depends_on: task-001
```

## Goal

All 7 Universal Core JSON Schema definitions authored and validated against the JSON Schema meta-schema. Pydantic models generated from them via `datamodel-code-generator`. Schema validation is the only path to runtime data — no pipeline code bypasses it.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 2 (Universal Core Schemas)

## Dependencies

- task-001 (repository foundation, `make validate-schemas` target, `scripts/validate_schemas.py`)

## Acceptance criteria

- [ ] `schemas/universal/voice_axes.schema.json` — all 9 voice-axis categories, typed fields with units/ranges; validates against JSON Schema meta-schema
- [ ] `schemas/universal/structural_hierarchy.schema.json` — GenericUnit + specialized Beat/Scene/Chapter/Act/Book/Series via `$ref`/`allOf`; validates
- [ ] `schemas/universal/continuity_model.schema.json` — Character, Location, Object, Concept, Faction, Timeline; validates
- [ ] `schemas/universal/promise_ledger.schema.json` — Promise object with all 9 promise types (foreshadowing, chekhov_object, character_question, mystery_thread, emotional_debt, thematic_setup, romantic_tension, world_question, series_thread); validates
- [ ] `schemas/universal/ai_tell_catalog.schema.json` — pattern entry with severity 1–5, context flags, includes 4 MBSE additions (triple restatement, abstract emotion-labeling, "It is X a Y" construction, prose explaining itself); validates
- [ ] `schemas/universal/specificity_heuristics.schema.json` — metric definitions; validates
- [ ] `schemas/universal/convergence.schema.json` — Convergence Controller decision rule: GO / REVISE / RE-PLAN / FORCE-RESOLVE with conditions; Sensitivity violation → RE-PLAN only encoded as constraint; validates
- [ ] `scripts/validate_schemas.py` (real implementation): validates all schemas against JSON Schema meta-schema; validates pydantic models round-trip; exits non-zero on any failure
- [ ] `make validate-schemas` calls the real validate_schemas.py and passes clean
- [ ] Pydantic models generated: `datamodel-code-generator --input schemas/universal/ --output pipeline/schemas/universal/`
- [ ] Round-trip test for each schema: load YAML fixture → validate → instantiate pydantic model → serialize → re-validate
- [ ] Invalid fixture tests: validation correctly rejects malformed examples
- [ ] Test fixtures in `tests/fixtures/universal/`: valid + invalid examples for each of the 7 schemas
- [ ] All tests pass with `make test`
- [ ] `make validate-schemas` passes on clean checkout

## Subtasks

- T2.1 — Author `schemas/universal/voice_axes.schema.json`. Group fields by: sentence-level (sentence_length_mean/std/distribution, sentence_opener_distribution), lexical (lexical_diversity_ttr, formality_register, concrete_noun_ratio, adverb_density), syntactic (clause_complexity, subordinate_clause_ratio), dialogue (dialogue_ratio, dialogue_tag_style), sensory (sensory_token_density_per_1k, modality_distribution), pacing (interiority_pct, exposition_pct, action_pct), metaphor (metaphor_density, metaphor_domain_distribution), subtext (subtext_weight, showing_telling_ratio), cadence (em_dash_density, em_dash_per_1k_max, punctuation_rhythm), forbidden_constructions (list of regex patterns), enforcement_weights (per-axis float 0–1). All numeric fields get `minimum`/`maximum` and `x-unit` annotation. `additionalProperties: false`.
- T2.2 — Author `schemas/universal/structural_hierarchy.schema.json`. Base `GenericUnit`: id, parent_unit_id, unit_type (enum: book/act/chapter/scene/beat), target_word_count (min/max object), actual_word_count, function, state (enum: planned/drafted/in_review/committed/force_resolved), created_at, updated_at. Specialized via `allOf`: Beat adds beat_type + tension_value; Scene adds scene_function + pov_character_id + heat_level + ledger_snapshot_ref; Chapter adds chapter_number + hook_present; Act adds act_number + act_function; Book adds book_number + word_count_target; Series adds series_id + book_count_target.
- T2.3 — Author `schemas/universal/continuity_model.schema.json`. Entities: Character (id, name, role, arc_position, core_belief_current, core_belief_true, wound_state, relationships, voice_signature, forbidden_phrases), Location (id, name, type, established_facts, spatial_relationships), Object (id, name, chekhov_state, established_properties), Concept (id, name, thematic_function, first_introduced_at), Faction (id, name, members, goals, power_dynamic), Timeline (events list with event_id/chapter/scene/description/characters_present). Bible: collection of all entity lists + last_updated + content_hash.
- T2.4 — Author `schemas/universal/promise_ledger.schema.json`. Promise object: id, type (enum: foreshadowing/chekhov_object/character_question/mystery_thread/emotional_debt/thematic_setup/romantic_tension/world_question/series_thread), description, opened_at (chapter + scene), must_resolve_by (chapter), resolution_state (enum: open/partially_resolved/resolved/overdue/force_resolved), resolution_scene, notes, weight. Ledger: list of Promise + metadata (book_id, generated_at, total_open, total_overdue).
- T2.5 — Author `schemas/universal/ai_tell_catalog.schema.json`. PatternEntry: pattern_id, pattern_text (regex or description), severity (integer 1–5), context_flags (list of strings: "always_bad"/"dialogue_ok"/"narration_only"/etc.), description, examples_bad (list), examples_good (list). Catalog: list of PatternEntry + version. Include baseline patterns from Starter §6 plus the 4 MBSE additions: triple_restatement, abstract_emotion_labeling, it_is_x_a_y_construction, prose_explaining_itself.
- T2.6 — Author `schemas/universal/specificity_heuristics.schema.json`. MetricDef: metric_id, metric_name, description, measurement_unit, target_range (min/max), measurement_method (enum: deterministic/llm_scored/hybrid), applicable_to (list of unit_types). Catalog: list of MetricDef + version.
- T2.7 — Author `schemas/universal/convergence.schema.json`. DecisionRule: condition (string expression), action (enum: GO/REVISE/RE-PLAN/FORCE-RESOLVE), reason_code, max_revise_attempts, notes. Hard constraint encoded as a rule: `{"condition": "sensitivity_violation == true", "action": "RE-PLAN", "notes": "Sensitivity violations cannot be FORCE-RESOLVED — sacred constraint"}`. ConvergenceConfig: list of DecisionRule + budget_exhausted_action (must be FORCE-RESOLVE) + max_global_revisions.
- T2.8 — Implement real `scripts/validate_schemas.py`: iterate all `schemas/**/*.schema.json`, validate each against Draft-7 meta-schema via `jsonschema.Draft7Validator.check_schema()`, run pydantic model round-trip for each schema that has a generated model. Exit 1 on first failure with descriptive message.
- T2.9 — Update `Makefile` `validate-schemas` target to call the real script.
- T2.10 — Generate pydantic models: `datamodel-codegen --input schemas/universal/ --output pipeline/schemas/universal/ --input-file-type jsonschema --output-model-type pydantic_v2.BaseModel`. Commit generated files. Do not hand-edit generated output.
- T2.11 — Write test fixtures: `tests/fixtures/universal/{voice_axes,structural_hierarchy,continuity_model,promise_ledger,ai_tell_catalog,specificity_heuristics,convergence}_{valid,invalid}.json` (14 fixture files).
- T2.12 — Write tests `tests/unit/schemas/test_universal_schemas.py`: for each schema, test_valid_fixture_validates, test_invalid_fixture_rejected, test_pydantic_round_trip.
- T2.13 — Commit: `feat(schemas): universal core schemas v1 (task-002)`.

## Key decisions that affect this task

- **Schemas are the contract (DEC-007):** `additionalProperties: false` on all schemas. No runtime data bypasses schema validation.
- **Sensitivity violations → RE-PLAN (DEC-005):** This constraint must be encoded explicitly in `convergence.schema.json` — the schema is authoritative, not just a comment.
- **Pydantic models generated from schema:** `datamodel-code-generator` is the single source of truth. Do not hand-write pydantic models for universal schemas.
- **4 MBSE AI-tell additions:** triple restatement, abstract emotion-labeling, "It is X a Y" construction, prose explaining itself — all must appear in `ai_tell_catalog.schema.json`.

## Suggested approach

1. Read `Starter: docs/core-ontology-v3.md §2–8` for all axis definitions before authoring any schema.
2. Author voice_axes.schema.json first — it's referenced by almost everything else.
3. Author structural_hierarchy using `$ref`/`allOf` recursive pattern (see Starter task-002 suggested approach).
4. Author the remaining 5 schemas.
5. Run `python scripts/validate_schemas.py` after each schema to catch errors early.
6. Generate pydantic models after all 7 schemas pass.
7. Write fixtures (valid + invalid) for each schema.
8. Write tests; run `make test`.
9. Run `make validate-schemas`; verify clean.
10. Commit.

## Decisions to log in DECISIONS.md

- Pydantic generation strategy (generated vs hand-written).
- Schema versioning approach (`$id` field with version slug).
- `additionalProperties: false` strictness policy (recommend: yes for all V1 schemas).
- JSON Schema draft version choice (recommend: Draft-7 for widest tool support).

## Notes

- Voice Axes is the largest schema. Take time — every downstream profile and agent references its field names.
- The convergence schema encodes logic, not just data shapes. The sensitivity RE-PLAN constraint is a hard rule that must appear here.
- Do not author any profile data in this task — that is Phase 4/5.
- Generated pydantic files go in `pipeline/schemas/universal/`. Do not edit them; fix the source schema and regenerate.

## Out of scope

- Ledger schemas (Phase 3 — `schemas/ledgers/`)
- Profile schemas (Phase 4 — `schemas/profiles/`)
- Profile data files (Phase 5 — `profiles/`)
- Any pipeline code
