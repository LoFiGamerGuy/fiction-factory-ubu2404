# Task 005 — Profile Library (V1)

```
status: pending
started:
completed:
phase: 5
estimated_hours: 6-10
depends_on: task-004
```

## Goal

Authored profile data files for V1 genres and use cases. These are YAML data files, not code. All files validate against the Phase 4 profile schemas. Romance Module v1.0, Erotica subtype, Thriller v0.1 scaffold, and supporting sensitivity/goal/audience profiles are ready for pipeline use.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 5 (Profile Library V1)

## Dependencies

- task-004 (profile schemas + ProfileRegistry — all 5 profile schemas must exist and validate before data files can be authored)

## Acceptance criteria

- [ ] `profiles/author/default.yaml` — placeholder voice profile; validates against author_profile.schema.json; user must fill voice axes before first production run (comment block explains this)
- [ ] `profiles/genre/romance_module_v1.yaml` — full Romance Module v1.0; validates
- [ ] `profiles/genre/erotica_module_v1.yaml` — Erotica / High-Heat subtype; validates; produces distinct ProjectSpec from romance_module_v1 (heat_curve and interiority_budget differ)
- [ ] `profiles/genre/thriller_module_v01.yaml` — Thriller scaffold v0.1; validates; `genre_module_status: scaffold` flag set; comment block warns "NOT production-validated"
- [ ] `profiles/sensitivity/default.yaml` — default content policy (permissive baseline; user tightens per series); validates
- [ ] `profiles/goal/kdp_commercial.yaml` — KDP commercial fiction goal profile; validates
- [ ] `profiles/audience/romance_reader.yaml` — romance reader persona set; validates
- [ ] `profiles/audience/erotica_reader.yaml` — erotica reader persona set; validates
- [ ] `make validate-schemas` covers all profile YAML files and passes clean
- [ ] ProfileRegistry integration test: loads all V1 profiles cleanly without schema errors
- [ ] Composition test: Romance + romance_reader + kdp_commercial + default sensitivity → valid ProjectSpec
- [ ] Composition test: Erotica + erotica_reader + kdp_commercial + default sensitivity → valid ProjectSpec with distinct heat_curve and interiority_budget_pct_max = 0.20
- [ ] Thriller scaffold: loads without schema error; `genre_module_status == "scaffold"` in loaded model
- [ ] `make test` passes

## Subtasks

- T5.1 — Author `profiles/author/default.yaml`. All voice axis fields present with placeholder values (e.g., `sentence_length_mean: null`, `enforcement_weights: {}`). Large comment block at top: "This is a placeholder profile. Fill in your voice axes before first production run. See docs/profile-axis-framework-v2.md for guidance." Set `profile_id: "author_default_placeholder"`, `version: "0.1"`.
- T5.2 — Author `profiles/genre/romance_module_v1.yaml`. Per MBSE Craft Reviews Acceptance §2.1: `genre_module_status: validated`. Required fields: heat_scale (1–5, anchors: 1=sweet/closed-door, 2=sensual/off-page, 3=sensual/on-page, 4=explicit, 5=erotic). Structural conventions: word_count_range 60000–110000, chapter_count_range 25–35. Required scene slots: meet_cute (ch 1–2), inciting_romantic_conflict (by ch 7), midpoint_emotional_peak (at 0.5 of book), dark_moment / black_moment (at 0.7), grand_gesture (at 0.85–0.9), HEA_or_HFN_resolution (at 0.95–1.0). heat_curve: rising from 1 at open to heat_level at midpoint, maintaining through escalation. sex_scene_spec: required when heat ≥ 3. Reader contract promises: romantic_tension, emotional_debt, HEA_or_HFN. Consent arc required. Taboos: cheating_without_full_redemption, unhealthy_power_dynamic_presented_uncritically. Quality gates: convention_compliance ≥ 0.90, promise_resolution_rate = 1.0.
- T5.3 — Author `profiles/genre/erotica_module_v1.yaml`. `genre_module_status: validated`. Extends romance pattern. Key distinctions: heat_level = 5 (erotic), heat_curve = steep (first sex scene by chapter 2), interiority_budget_pct_max: 0.20, exposition_budget_pct_max: 0.15, sex_scene_frequency_min: "1_per_3_chapters", escalation_rules: no repeated act_type (from IntimacyEscalationLedger) within last 3 sex scenes, sex_scene_spec required (every scene needs choreography, sensory density elevated). Structural conventions: word_count_range 40000–80000. Sensitivity note in comments: "Sensitivity profile controls ultimate hard limits; this genre profile sets pacing targets within those limits."
- T5.4 — Author `profiles/genre/thriller_module_v01.yaml`. `genre_module_status: scaffold`. Comment block: "NOT production-validated. Scaffold only — do not use for production runs without author validation. See IMPLEMENTATION_PLAN.md Phase 5 notes." Fields present but with placeholder values: knowledge_state_per_character (list placeholder), evidence_object_ledger (placeholder), relationship_entries_true_vs_performed (placeholder), thriller_engine_block_per_scene (placeholder). quality_gates: empty list (scaffold). Required scene slots: minimal set (inciting_incident, midpoint_revelation, climax, resolution).
- T5.5 — Author `profiles/sensitivity/default.yaml`. `profile_id: "sensitivity_default"`, `version: "1.0"`, `sacred: true`. Content domain policies: sexual_content: allow, violence: allow, profanity: allow, substance_use: allow, minors_in_sexual_context: prohibit (absolute sacred floor). Vocabulary restrictions: empty list (user adds per series). Hard thresholds: max_heat: 5 (permissive default; user tightens to 3 or 2 for target market). Comment block: "This is a permissive baseline. Tighten per series in your series spec. max_heat can only be lowered, never raised by Goal profile."
- T5.6 — Author `profiles/goal/kdp_commercial.yaml`. `intent: kdp_high_revenue`. Conflict precedence rules: voice_axes [genre, audience, author, universal], pacing [goal, genre, universal], length [goal, genre, universal]. Weight overrides: critic_weights {convention_critic: 1.5, ai_tell_critic: 1.5, pacing_critic: 1.3}, reader_weights {target_demo: 1.3}. Success criteria: convention_compliance ≥ 0.90, promise_resolution_rate: 1.0, pacing_score ≥ 0.80.
- T5.7 — Author `profiles/audience/romance_reader.yaml`. 4 reader personas: target_demo (KU subscriber, reads 3+ romance/month, HEA required, low ambiguity tolerance), genre_veteran (knows tropes, catches continuity errors, marks DNF if tropes mishandled), emotional_probe (tracks affect arc, marks satisfaction if emotional payoff lands), detail_reader (catches continuity errors, values specificity). DNF triggers: no romantic tension by chapter 3, HEA seems impossible at 0.75. Satisfaction triggers: chemistry established by chapter 2, grand gesture lands.
- T5.8 — Author `profiles/audience/erotica_reader.yaml`. 3 reader personas: heat_seeker (explicit content required by chapter 2, marks DNF if heat stalls), pacing_reader (wants escalation, not repetition, checks act_type variety), world_reader (cares about character consistency through sex scenes). DNF triggers: same act_type repeated within 3 consecutive sex scenes, heat level drops after peak without plot reason. Satisfaction triggers: escalation clear and steady, sensory density high throughout.
- T5.9 — Update `scripts/validate_schemas.py` to also validate all `profiles/**/*.yaml` files against their respective profile schemas. Verify `make validate-schemas` covers them.
- T5.10 — Write integration test `tests/integration/test_profile_library.py`: ProfileRegistry.compose() for Romance pentad → valid ProjectSpec; for Erotica pentad → valid ProjectSpec with interiority_budget_pct_max = 0.20 and heat_curve steep; Thriller scaffold loads without error and genre_module_status == "scaffold"; all 8 profile files validate individually.
- T5.11 — Commit: `feat(profiles): V1 profile library — Romance v1.0, Erotica v1.0, Thriller scaffold, default sensitivity/goal/audience (task-005)`.

## Key decisions that affect this task

- **Erotica as Genre Module subtype (decisions.md 2026-05-14 §2.4 LOCKED):** Erotica is a parameterization within the commercial track — not a separate track. `interiority_budget_pct_max: 0.20`, `exposition_budget_pct_max: 0.15`, explicit sex scene frequency enforcement via `sex_scene_frequency_min`.
- **Sensitivity thresholds are sacred (DEC-005):** The `default.yaml` sensitivity profile sets the absolute floor. `minors_in_sexual_context: prohibit` must appear and cannot be overridden by any goal profile.
- **Thriller scaffold flag:** `genre_module_status: scaffold` is the machine-readable signal that pipeline can detect and warn at run time. Do not use scaffold genre for production runs.
- **No prose retention (DEC-003):** Voice profile axes are measured/designed — no extracted prose quotations in any profile file.

## Suggested approach

1. Author `romance_module_v1.yaml` first — it is the most complete and most referenced.
2. Author `erotica_module_v1.yaml` second — extends romance pattern; verify distinct ProjectSpec in test.
3. Author thriller scaffold — minimal, flagged.
4. Author sensitivity, goal, audience profiles.
5. Author `default.yaml` author placeholder last.
6. Update `validate_schemas.py` to cover YAML files.
7. Write integration test; run `make test && make validate-schemas`.
8. Commit.

## Decisions to log in DECISIONS.md

- Author profile as placeholder rather than synthetic voice (per user's use case — user fills in their own axes).
- Default sensitivity as permissive baseline (user tightens per series — not hardcoded restrictive).
- Erotica as genre module vs separate track (already decided at §2.4 gate; cite that decision).
- Thriller scaffold status field as machine-readable gate (not just a comment).

## Notes

- These are data files, not code. The goal is valid, consistent, well-commented YAML that a human author can understand and edit.
- Romance Module v1.0 is the primary production-validated profile. All V1 testing runs against it.
- Erotica v1.0 directly addresses the pacing failure mode: the low interiority budget and sex_scene_frequency_min enforce pacing in the profile, not in ad hoc code.
- Thriller v0.1 is scaffold only. It is included so the system can load it without errors, but it should not be used for production manuscript generation until a working author validates it.
- All profile YAML files will be edited by the user (especially voice axes, sensitivity thresholds). Comments in YAML are part of the deliverable — they explain what each field does.

## Out of scope

- Literary fiction, science fiction, fantasy genre modules (V2 roadmap — Phase 15)
- Additional sensitivity profiles beyond default (user authors per series)
- Real author voice extraction (Phase 14 Mem0 integration enables this in V2)
- Critic/reader profile authoring beyond the personas in audience profiles
