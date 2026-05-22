# Implementation Plan — Autonomous Fiction Pipeline

**Status:** Phase 0 (review + synthesis) complete. Phases 1–14 are the implementation sequence.  
**Architecture decision:** Shared core + per-track genre modules. Source bundles: MBSE, Starter, Bunko, Manus-Agnostic.  
**Synthesis shape:** Starter Universal Core ontology + Manus-Agnostic code foundation + MBSE Genre Module Architecture + Bunko Voice Profile schema + Paperclip/WUPHF/ROMA/EvoSkill control stack.  
**Plan-of-record:** `/home/gosne/.claude/plans/in-this-folder-you-deep-toast.md`  
**Decisions log:** `memory/decisions.md` (authoritative) + `DECISIONS.md` (append-only, per Starter DEC-NNN format)

---

## How to use this plan

Each phase has:
- **Goal** — what the phase delivers
- **Source** — which bundle(s) the design derives from
- **Tasks** — concrete sub-deliverables  
- **Acceptance** — verifiable gate before moving to next phase
- **References** — which docs to consult

**Model tier during development:** Use `model_tier = test` (Haiku 4.5, gpt-4.1-mini, Ollama phi3.5) for all LLM calls until Phase 14 says otherwise. This saves API credits while validating architecture correctness.

**Do not skip ahead.** Each phase is foundational to the next.

---

## Pre-implementation standing decisions (non-negotiable)

From Starter (DEC-000-1 through DEC-000-7) + synthesis decisions:

1. **V1 Primary Profile Axes:** Author × Genre × Audience × Goal × Sensitivity
2. **Conflict precedence:** Constraint > Sensitivity > Goal > Genre > Audience > Author > Universal
3. **No prose retention from external sources.** Voice extraction = measurement only. Source prose enters, axes computed, prose discarded.
4. **No human gates in inner generation loop.** Convergence Controller is fully autonomous. Two human gates only: spec authoring + post-run review.
5. **Sensitivity Profile thresholds are sacred.** Goal cannot loosen them. Sensitivity violations cannot be FORCE-RESOLVED — they trigger RE-PLAN.
6. **Reproducibility first-class.** Every run pins: seed, model version, profile version, registry snapshot. Same inputs + seed = bit-identical outputs.
7. **Schemas are the contract.** Every component input/output validates against a schema. Schema validation failures auto-retry, then become FORCE-RESOLVE entries with logging.
8. **Heavier-weight, more robust from the start.** Under full-auto operation every silent-failure path becomes a manuscript-corruption path. Where two paths exist, choose the more robust one. (MBSE Reviewer Response §4.)
9. **Model tiering.** `test` tier (Haiku/gpt-mini/Ollama) during development; `production` tier (Sonnet drafter / Opus critics) only after architecture is stable.
10. **BookMetricsLedger + 9 additional ledgers** track running cumulative state (not per-scene averages). QualityAgent evaluates contribution to running total, not local absolute value.
11. **Author Dashboard** is a Phase 13 deliverable: live monitoring + historical browse, FastAPI backend + React frontend (extending manus-agnostic TSX shell).

---

## Pre-Phase-1 — Baseline Archive (before implementation begins)

**Gate action.** Before any Phase 1 work, create a `fiction-factory-baseline-YYYYMMDD.tar.gz` in the workspace root containing the complete post-synthesis, pre-implementation state. This is the restorable baseline for everything agreed during review (Phases 0–4).

**Contents of the archive:**
- Workspace root: `IMPLEMENTATION_PLAN.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `glossary.md`, `CLAUDE.md`
- `schemas/` — all 25 stub JSON schemas
- `tasks/` — all 15 task backlog files
- `.workspace/TOOLING_DECISIONS.md`, `.workspace/COMPARISON.md`, `.workspace/TIMELINE.md`, `.workspace/MANUS_TRIAGE_SUMMARY.md` — key review artifacts
- Original zips: `*.zip` (already committed in git, but included in archive for portability)
- Memory files: `/home/gosne/.claude/projects/-home-gosne-src-workspace-Systems-Architecture/memory/` — all `.md` files

**Command (run from workspace root):**
```bash
tar -czf fiction-factory-baseline-$(date +%Y%m%d).tar.gz \
  IMPLEMENTATION_PLAN.md ARCHITECTURE.md DECISIONS.md glossary.md CLAUDE.md \
  schemas/ tasks/ \
  .workspace/TOOLING_DECISIONS.md .workspace/COMPARISON.md .workspace/TIMELINE.md \
  .workspace/MANUS_TRIAGE_SUMMARY.md \
  *.zip \
  -C /home/gosne/.claude/projects/-home-gosne-src-workspace-Systems-Architecture memory/
```

**Acceptance.** Archive exists, non-empty, extractable. Do not begin Phase 1 until this is confirmed.

---

## Phase 1 — Repository Foundation

**Goal.** Working repo skeleton with conventions, tooling, and test harness.

**Source.** Starter (Phase 0 / task-001). Manus-agnostic (orchestrator refactor pattern).

**Tasks.**
- T1.1 — `pyproject.toml` with all V1 dependencies (see TOOLING_DECISIONS.md Adopt list).
- T1.2 — Directory structure (see `ARCHITECTURE.md §Directory layout`).
- T1.3 — `Makefile`: targets `lint`, `test`, `validate-schemas`, `run-pipeline`, `dashboard`.
- T1.4 — `mypy --strict`, `ruff check/format`, `pre-commit` hooks (lint + mypy + schema validator).
- T1.5 — `pytest` with coverage; smoke test stub.
- T1.6 — `.env.example` (ANTHROPIC_API_KEY, OPENAI_API_KEY, OLLAMA_HOST).
- T1.7 — `model_router.json` defaulting to `test` tier.
- T1.8 — `DECISIONS.md` at repo root (Starter DEC-NNN format). Pre-populate with the 11 standing decisions above.
- T1.9 — `Ollama`: `ollama pull phi3.5` (test-tier local model).
- T1.10 — Install all Adopt tools: `uv pip install anthropic openai instructor pydantic jsonschema datamodel-code-generator pyyaml pytest pytest-cov mypy ruff pre-commit deepeval langgraph roma-dspy mem0ai scikit-learn scipy sentence-transformers numpy spacy nltk lexicalrichness textstat vaderSentiment faststylometry booknlp && python -m spacy download en_core_web_sm`.
- T1.11 — Stand up Paperclip (Docker) and WUPHF (binary) locally. Create first "series" company in Paperclip. Create WUPHF workspace with `series-bible` wiki and `pipeline` channel.
- T1.12 — Claude Managed Agents foundation: Create `pipeline/core/managed_agent_config.py`. Add `managed_agent_mode: bool` and `persistent_memory_path: str` to AgentContext. Wire Claude API client for persistent memory, Files API hooks, Message Batches API support. Fixture test: AgentContext instantiates with managed_agent_mode=True/False.
- T1.13 — Mem0 semantic retrieval (moved from Phase 14): Create `pipeline/core/bible_semantic_store.py` wrapper. Wire ContextPackBuilder stub method `get_bible_context_semantic(query, top_k=5)`. Seed fixture bible (3 characters, 2 locations). Test: query "Sarah's occupation" returns top-5 relevant facts. Document token savings vs full-bible injection.
- T1.14 — Dreaming evaluation fixture: Create `tests/fixtures/dreaming_eval/` with 3-scene Romance Module fixture (meet-cute → first-date → first-conflict). Smoke test runner with `--with-dreaming` and `--without-dreaming` flags. No agent implementation yet — just test harness.
- T1.15 — Decision gate documentation: Create `docs/bcr-decisions/dreaming-vs-evoskill.md` template with criteria (convergence speed, prose quality VoiceConsistencyMetric, routing decision count). Gate after Phase 7 smoke test. Outcomes: (1) Dreaming only, (2) EvoSkill only, (3) Both.

**Acceptance.** `make lint && make test` passes on hello-world. Pre-commit hooks fire on commit. Paperclip heartbeat green. WUPHF channel accessible. AgentContext instantiates with `managed_agent_mode=True` without errors. Mem0 semantic retrieval: query fixture bible → returns top-5 facts with >80% relevance. Dreaming evaluation harness: `pytest tests/fixtures/dreaming_eval/` passes (no agents wired yet). `docs/bcr-decisions/dreaming-vs-evoskill.md` exists with decision criteria.

---

## Phase 2 — Universal Core Schemas

**Goal.** JSON Schema definitions for all Universal Core entities. Pydantic models generated from them. Schema validation is the only path to runtime data.

**Source.** Starter (`docs/core-ontology-v3.md` Part I). MBSE (`schemas/v1/`, Phase 0B plan).

**Tasks.**
- T2.1 — `schemas/universal/voice_axes.schema.json` — all voice axis fields with types, ranges, units. Ref: `core-ontology-v3.md §2`.
- T2.2 — `schemas/universal/structural_hierarchy.schema.json` — Generic Unit, Beat, Scene, Chapter, Act, Book, Series. Ref: `§3`.
- T2.3 — `schemas/universal/continuity_model.schema.json` — Bible entities: Character, Location, Object, Concept, Faction, Timeline. Ref: `§4`.
- T2.4 — `schemas/universal/promise_ledger.schema.json` — Promise object with all types (foreshadowing, chekhov_object, character_question, mystery_thread, emotional_debt, thematic_setup, romantic_tension, world_question, series_thread). Ref: `§5`.
- T2.5 — `schemas/universal/ai_tell_catalog.schema.json` — pattern entry with severity 1–5 and context flags. Ref: `§6`. Include the 4 additions from MBSE craft reviews (triple restatement, abstract emotion-labeling, "It is X a Y" construction, prose explaining itself).
- T2.6 — `schemas/universal/specificity_heuristics.schema.json` — metric definitions. Ref: `§7`.
- T2.7 — `schemas/universal/convergence.schema.json` — Convergence Controller decision rule: GO / REVISE / RE-PLAN / FORCE-RESOLVE with conditions. Sensitivity violations → RE-PLAN only. Ref: `§8`.
- T2.8 — `scripts/validate_schemas.py` — validates all schemas against JSON Schema meta-schema; validates pydantic models round-trip.
- T2.9 — `make validate-schemas` target calls T2.8.
- T2.10 — Generate pydantic models: `datamodel-code-generator --input schemas/universal/ --output pipeline/schemas/universal/`.

**Acceptance.** All 7 schemas validate against JSON Schema meta-schema. Pydantic models exist for each. Round-trip test: load YAML fixture → validate → serialize → re-validate. `make validate-schemas` passes clean.

**References.** `Starter: docs/core-ontology-v3.md §2–8`, `MBSE: schemas/v1/` (Phase 0B plan).

---

## Phase 3 — Ledger System

**Goal.** All 10 ledgers implemented as append-only SQLite event logs with schemas and a LedgerManager that produces the Author Dashboard summary for every scene's context pack.

**Source.** New design (synthesis decision). Inspired by Starter PromiseLedger pattern. Stylometric dimensions from MBSE `quantifiable_metrics.md` and Bunko Voice Profile schema §8.

**Tasks.**
- T3.1 — `schemas/ledgers/book_metrics_ledger.schema.json` — event schema for each finalized scene: interiority_pct, sensory_density_per_1k, em_dash_density, dialogue_ratio, heat_curve_position, ai_tell_count, no_fly_violations, sex_scene_flag, sex_scene_count_running, sentence_length_avg, exposition_pct, action_pct, word_count, chapter_id, scene_id.
- T3.2 — `schemas/ledgers/character_arc_ledger.schema.json` — per-character arc event: character_id, arc_position (opening/wound_open/processing/wound_healing/resolved), wound_state, core_belief_current, core_belief_true, relationship_states (dict: other_char_id → status).
- T3.3 — `schemas/ledgers/intimacy_escalation_ledger.schema.json` — per character pair: pair_id, events list (chapter, scene, act_type: first_touch/first_charged_moment/first_kiss/first_explicit/escalation_peak, heat_level, notes).
- T3.4 — `schemas/ledgers/reader_information_state.schema.json` — revelation events: fact_id, revealed_at (chapter/scene), known_by_reader: bool, known_by_characters: list[char_id], irony_type (dramatic/tragic/situational/none), notes.
- T3.5 — `schemas/ledgers/subplot_ledger.schema.json` — subplot events: subplot_id, type (romantic/professional/family/external), opened_at, target_resolution_chapter, status (open/escalating/complicating/resolved), resolution_scene.
- T3.6 — `schemas/ledgers/trope_commitment_ledger.schema.json` — trope events: trope_id, genre_module, activated_at, required_beats list (beat_id, description, target_chapter, status: pending/fulfilled/overdue).
- T3.7 — `schemas/ledgers/series_promise_ledger.schema.json` — cross-book promise events: promise_id, type, opened_book, opened_chapter, must_resolve_by_book, resolution_status.
- T3.8 — `pipeline/ledgers/ledger_manager.py` — LedgerManager: wraps all 10 ledgers, provides `update(scene_result)` and `get_dashboard_summary(book_id, scene_id) → AuthorDashboard` (structured summary for context pack injection).
- T3.9 — `pipeline/ledgers/book_metrics_ledger.py` — BookMetricsLedger: SQLite-backed append-only log, `compute_running_totals()`, `budget_remaining(target, word_count_remaining)`.
- T3.10 — Implement remaining 9 ledger classes (same SQLite-backed pattern).
- T3.11 — Scene Rhythm Ledger: rolling window of last 10 scene types (no schema needed — just a list maintained in LedgerManager state).
- T3.12 — `pipeline/ledgers/quality_evaluator.py` — QualityEvaluator that evaluates scene's **contribution to running total** not local value: `evaluate_scene_contribution(scene_metrics, running_totals, targets, word_count_remaining)`.

**Acceptance.** All 7 schemas validate. LedgerManager correctly updates all ledgers after a fixture scene. `get_dashboard_summary()` returns a structured summary with all 10 ledger states. QualityEvaluator passes a high-interiority scene when running total is below target.

**References.** Starter `core-ontology-v3.md §5` (PromiseLedger pattern), MBSE `quantifiable_metrics.md`, Bunko `BUNKO-VOICE-PROFILE-SCHEMA-v0.1.yaml §8`.

---

## Phase 4 — Profile System

**Goal.** All 5 primary profile schemas + conflict resolution engine. Profiles are data; code reads them.

**Source.** Starter (`docs/profile-axis-framework-v2.md`, `core-ontology-v3.md §9–13`). Bunko (Voice Profile schema §1–15). MBSE (Genre Module Architecture).

**Tasks.**
- T4.1 — `schemas/profiles/author_profile.schema.json` — voice axes YAML profile: all 9 axis categories from Bunko schema (sentence-level, lexical, syntactic, dialogue, sensory, pacing, metaphor, subtext, cadence, forbidden_constructions, enforcement weights).
- T4.2 — `schemas/profiles/genre_profile.schema.json` — genre module: scene_function_vocabulary, required_scene_slots, quality_gates, self_audit_rubric, heat_scale, structural_conventions, trope_library, reader_contract.
- T4.3 — `schemas/profiles/audience_profile.schema.json` — reader lens, tolerance bands, expectation set, trigger sets, reader personas (3–5 named personas with reading preferences).
- T4.4 — `schemas/profiles/sensitivity_profile.schema.json` — content domain policies, vocabulary restrictions, audience markers, hard thresholds. Mark all as sacred — Goal cannot loosen.
- T4.5 — `schemas/profiles/goal_profile.schema.json` — intent (kdp_high_revenue, literary_award_target, personal_vanity), conflict precedence rules, weight overrides for critics/readers, success criteria.
- T4.6 — `pipeline/profiles/profile_registry.py` — ProfileRegistry: loads profiles by type + name, composes them per conflict precedence, produces a `ProjectSpec` (the composed result all agents read).
- T4.7 — `pipeline/profiles/conflict_resolver.py` — implements Constraint > Sensitivity > Goal > Genre > Audience > Author > Universal precedence. Handles per-field overrides. Logs all conflicts resolved to DECISIONS.md.
- T4.8 — Tests: resolution of all conflict cases; sacred Sensitivity thresholds cannot be overridden by Goal; round-trip load → compose → serialize.

**Acceptance.** All 5 schemas validate. ProfileRegistry composes a ProjectSpec from fixture profiles. Conflict tests pass (all 6 precedence levels). Sensitivity sacred threshold test: Goal cannot loosen it. `make test` passes.

**References.** Starter `profile-axis-framework-v2.md`, `core-ontology-v3.md §9–13`. Bunko `BUNKO-VOICE-PROFILE-SCHEMA-v0.1.yaml`.

---

## Phase 5 — Profile Library (V1)

**Goal.** Authored profile files for V1 genres and use cases. These are data files, not code.

**Source.** MBSE (`Craft Reviews Acceptance — Plan of Record.md`). Bunko (Voice Profile schema as template). Starter (profile format).

**Tasks.**
- T5.1 — `profiles/author/default.yaml` — placeholder voice profile (user fills in before first production run).
- T5.2 — `profiles/genre/romance_module_v1.yaml` — Romance Module v1.0 per MBSE Craft Reviews Acceptance: HEA/HFN required, heat_level (RWA scale) + tonal_mode split, sex_scene_spec when heat ≥ sensual, heat_curve, meet_cute_spec, grand_gesture_spec, black_moment vs dark_night, consent_arc, power_dynamic_arc, required trope slots, scene_function_vocabulary.
- T5.3 — `profiles/genre/erotica_module_v1.yaml` — Erotica / High-Heat subtype: heat_level = erotic, steep heat_curve (first sex scene by chapter 2), interiority_budget_pct_max = 0.20, exposition_budget_pct_max = 0.15, sex_scene_frequency_min = 1_per_3_chapters, sex_scene_spec required, escalation rules (no repeated beat type within 3 scenes), per-scene sensory_density target elevated.
- T5.4 — `profiles/genre/thriller_module_v01.yaml` — Thriller Module v0.1 scaffold: knowledge_state per character, evidence_object ledger, relationship entries (true vs performed), thriller_engine block per scene. NOT production-validated — flag as scaffold.
- T5.5 — `profiles/sensitivity/default.yaml` — default content policy (all explicit content allowed by default; user tightens per series).
- T5.6 — `profiles/goal/kdp_commercial.yaml` — KDP commercial fiction: high velocity, heat escalation, reader-retention priority.
- T5.7 — `profiles/audience/romance_reader.yaml` and `profiles/audience/erotica_reader.yaml` — reader personas with tolerance bands and expectation sets.
- T5.8 — Validate all profile files against their schemas. `make validate-schemas` covers them.

**Acceptance.** All profile files validate. ProfileRegistry loads all V1 profiles cleanly. Romance Module + Erotica subtype produce distinct `ProjectSpec` compositions (heat_curve and interiority_budget differ). Thriller scaffold loads without errors but is flagged as unvalidated.

**References.** MBSE `Craft Reviews Acceptance — Plan of Record.md §2.1–2.2`. Bunko `BUNKO-VOICE-PROFILE-SCHEMA-v0.1.yaml §8`. User decision 2026-05-15 (erotica subtype requirements).

---

## Phase 6 — Agent Foundation

**Goal.** Core agent infrastructure: AgentContext dataclass, ModelRouter (multi-provider + model tiering), VoiceProfile (data-driven), ContextManager (3-tier), ContextPackBuilder (per-scene per-agent materialization with provenance).

**Source.** Manus-agnostic (ModelRouter, VoiceProfile, ContextManager, BaseAgent). MBSE Reviewer Response (AgentContext dataclass, ContextPackBuilder). Instructor (schema enforcement on all Claude calls).

**Tasks.**
- T6.1 — `pipeline/core/agent_context.py` — `AgentContext(project_layout, spec_loader, ledger_manager, log_path, output_dir, model_tier)` dataclass. Every agent constructor takes `AgentContext`. (MBSE Reviewer Response pattern; heavier than `agent_name` threading.)
- T6.2 — `pipeline/core/model_router.py` — port from manus-agnostic. Add: `model_tier` switching (test/production), Instructor wrapping on every call (replaces raw `response_format`), cost logging to `data/cost_log.jsonl`.
- T6.3 — `pipeline/core/voice_profile.py` — port from manus-agnostic. Extend with Bunko schema's 15 sections (forbidden_constructions regex, enforcement weights, calibration_history). Load from `profiles/author/` YAML.
- T6.4 — `pipeline/core/context_manager.py` — port from manus-agnostic. Extend with LedgerManager integration: three-tier context (scene/book/series) + Author Dashboard summary injected into every scene's context.
- T6.5 — `pipeline/core/context_pack_builder.py` — ContextPackBuilder: per-scene per-agent JSON materialization with provenance (source_file_hashes, view_schema_version, generated_at, agent_id). Implements the overlay + context-pack architecture from MBSE Agent Views doc.
- T6.6 — `pipeline/core/base_agent.py` — port from manus-agnostic. All agents inherit from this. `impl_class` attribute: deterministic / llm / hybrid.
- T6.7 — `pipeline/core/job_context.py` — `JobContext` typed dataclass (replaces plain dict job passing). All agents receive and return typed JobContext. (MBSE B3 fix.)
- T6.8 — `pipeline/core/project_layout.py` — `ProjectLayout` dataclass. Agents never assemble paths by hand. (MBSE B1 fix.)
- T6.9 — Tests: AgentContext construction; ModelRouter routes correctly per tier; VoiceProfile loads fixture profile; ContextManager respects size limits; ContextPackBuilder produces valid provenance JSON; BaseAgent run() contract.

**Acceptance.** All 6 core components instantiate without errors. ModelRouter routes `test` tier to Haiku/gpt-mini; `production` to Sonnet/Opus. ContextPackBuilder produces provenance JSON with all required fields. `make test` passes.

**References.** Manus-agnostic: `model_router.py`, `voice_profile.py`, `context_manager.py`, `base_agent.py`. MBSE: `Agent Views and Context Packs — Architecture Reference.md`. Bunko: `BUNKO-VOICE-PROFILE-SCHEMA-v0.1.yaml`.

---

## Phase 7 — Writing Pipeline Core

**Goal.** End-to-end scene generation: spec → writer → editor → quality gate → convergence. Scene lifecycle managed by LangGraph state machine. First smoke test milestone.

**Source.** Manus-agnostic (writer_agent, editor_agent, quality_agent). Starter (Convergence Controller §8). MBSE (orchestrator, NoFlyScanner, structural_analysis). LangGraph (state machine).

**Tasks.**
- T7.1 — Port `writer_agent.py` from manus-agnostic. Adapt to AgentContext + Instructor + ContextPack pattern.
- T7.2 — Port `editor_agent.py` from manus-agnostic. Integrate with VoiceProfile forbidden_constructions. Adapt to Instructor.
- T7.3 — Port `scanner.py` (NoFlyScanner) and `structural_analysis.py` from manus-agnostic. These are deterministic; no Instructor needed.
- T7.4 — Port `quality_agent.py` from manus-agnostic. Extend with:
  - `QualityEvaluator` from Phase 3 (running-total contribution scoring)
  - LedgerManager update after each finalized scene
  - Fail-closed: any evaluator exception → `needs_review`, never silent pass. (MBSE B11/B12 fix.)
- T7.5 — `pipeline/convergence_controller.py` — implement Starter §8: GO / REVISE / RE-PLAN / FORCE-RESOLVE. Sensitivity violations → RE-PLAN only (cannot FORCE-RESOLVE). Budget exhausted → FORCE-RESOLVE with log entry. Never halts.
- T7.6 — `pipeline/scene_state_machine.py` — LangGraph graph: nodes = lifecycle states (Unspecced, Specced, DirtyDraft, NeedsReview, Approved, Final). Edges = transitions with guard conditions. SQLite checkpointing (pause/resume).
- T7.7 — `pipeline/job_runner.py` — port from manus-agnostic. Integrate with LangGraph state machine. Model tier from AgentContext.
- T7.8 — `pipeline/spec_loader.py` — port from manus-agnostic. Add: `series_spec_path()` and `book_spec_path()` (MBSE B1 fix, already done in Phase 0A — verify present). Validate all loaded specs against JSON Schema. No sentinel strings survive validation (MBSE M2 fix).
- T7.9 — Smoke test (FIRST MILESTONE): write one scene end-to-end with test-tier models against a fixture series spec. Must: (a) parse scene spec, (b) call WriterAgent (Haiku), (c) call EditorAgent, (d) call QualityAgent, (e) produce `FINAL` scene output without errors, (f) update all 10 ledgers, (g) complete in under 90 seconds. No API key = fail-closed (never silent pass).

**Acceptance.** Smoke test passes (T7.9). LangGraph state machine transitions correctly through all 6 states. Convergence Controller correctly routes REVISE / RE-PLAN / FORCE-RESOLVE based on fixture inputs. Sensitivity violation → RE-PLAN (not FORCE-RESOLVE). Ledger updates after scene. `make test` passes.

**References.** Manus-agnostic: `writer_agent.py`, `editor_agent.py`, `quality_agent.py`, `job_runner.py`. Starter: `core-ontology-v3.md §8`. MBSE: `Reviewer Response §3 (B11/B12)`.

---

## Phase 8 — Specialist Agents

**Goal.** Full editorial pipeline: 9 specialist agents ported and integrated.

**Source.** Manus-agnostic (all 9 specialist agent files). MBSE (VoiceExemplarManager spec from Dr. Smith's review).

**Tasks.**
- T8.1 — Port `arc_reader_agent.py` and `arc_reader_packet_agent.py`. Adapt to AgentContext + Instructor.
- T8.2 — Port `drift_detector_agent.py`. Adapt to AgentContext + ContextPack.
- T8.3 — Port `developmental_editor_agent.py`, `line_editor_agent.py`, `copy_editor_agent.py`, `proofreader_agent.py`, `genre_norm_editor_agent.py`, `revision_agent.py`.
- T8.4 — `pipeline/voice_exemplar_manager.py` — implement per MBSE VoiceExemplarManager spec: 2 exemplars per call, 200–400w window, 3-tier source hierarchy, uniform random rotation, beat-type stratification hook, provenance per generated scene, collapse detector, hard invariant against auto-add of generated content.
- T8.5 — Integrate genre_norm_editor with GenreModule profile (reads genre_profile.yaml for scene-function vocabulary, required-scene enforcement, heat escalation rules).
- T8.6 — Tests: each specialist agent instantiates + runs against fixture input without error. VoiceExemplarManager hard invariant test: attempting to auto-add generated content raises ValueError.

**Acceptance.** All 9 specialist agents pass their unit tests. VoiceExemplarManager collapse-detector test. Genre norm editor enforces Romance Module v1.0 heat_curve check. `make test` passes.

**References.** Manus-agnostic: all 9 agent files. MBSE: `Reviewer Response §3 (M13)`, `Closure Note — Dr. Smith.md`.

---

## Phase 9 — Bible + Continuity Layer

**Goal.** Bible Steward (propose/validate/commit deltas), Loop Tracker (Promise + Series Promise Ledger deadline enforcement), integrated with Convergence Controller.

**Source.** Starter (`core-ontology-v3.md §4–5`). MBSE (`continuity_agent.py`, `series_arc_tracker.py`).

**Tasks.**
- T9.1 — `pipeline/continuity/bible_steward.py` — propose_delta, validate_delta (contradiction types: type-mismatch, timeline-violation, spatial, capability, voice, taboo), commit_delta (atomic os.replace + exclusive lock + append-only event log + content-hash chain + per-book snapshot), query.
- T9.2 — `pipeline/continuity/loop_tracker.py` — Promise Ledger enforcement: overdue detection (no chapter ships with overdue promises), deadline enforcement, series thread tracking (Series Promise Ledger for cross-book arcs).
- T9.3 — Integrate Bible Steward with Convergence Controller: Bible contradiction → RE-PLAN (hard fail). Overdue promise → REVISE (soft fail) up to N attempts, then RE-PLAN.
- T9.4 — Port manus-agnostic `continuity_agent.py` to the BibleSteward/LoopTracker architecture.
- T9.5 — Port manus-agnostic `series_arc_tracker.py`. Extend to write to Series Promise Ledger.
- T9.6 — Tests: bible contradiction test (commit a delta that conflicts with an existing fact → rejected). Overdue promise test (chapter attempts to ship with overdue promise → routing_decision = needs_review). Series arc update failure is fatal by default (MBSE policy: `publishing.require_series_arc_update: true`).

**Acceptance.** BibleSteward correctly rejects contradictory deltas. LoopTracker correctly flags overdue promises. Series arc update failure → fatal. Integration with Convergence Controller: contradiction → RE-PLAN. `make test` passes.

**References.** Starter `core-ontology-v3.md §4–5`. MBSE `continuity_agent.py`, `series_arc_tracker.py`, `Reviewer Response §3 (B8)`.

---

## Phase 10 — Book + Series Level

**Goal.** Book-level orchestration: spec-driven scene planning, structural verification, series arc management. Orchestrator becomes the top-level CLI.

**Source.** Manus-agnostic (orchestrator, job_runner, book_structure_planner, book_structural_verifier). MBSE (orchestrator commands, BookStructurePlanner, BookStructuralVerifier).

**Tasks.**
- T10.1 — Port `book_structure_planner.py` from manus-agnostic. Reads series + book spec → generates full scene inventory (act/chapter/scene assignments, word targets, heat level per scene from heat_curve).
- T10.2 — Port `book_structural_verifier.py` from manus-agnostic. Checks: word count, act proportions, scene count, heat_curve compliance, HEA/HFN (if Romance module), sex_scene frequency (if Erotica module), all RTM requirements.
- T10.3 — `pipeline/orchestrator.py` (thin CLI, manus-agnostic pattern) → `pipeline/job_runner.py` (pipeline execution). Commands: `--validate-spec`, `--init-book`, `--job`, `--resume`, `--verify-book`, `--book-publish`, `--status`.
- T10.4 — `pipeline/spec_validator_agent.py` — port from MBSE. Rewrite as thin wrapper over `jsonschema.validate` against the Phase 2 canonical schemas. Sentinel string check: reject any field equaling `"REQUIRED — fill in"`. (MBSE B4/B5 fix.)
- T10.5 — Ensure no agent assembles a path by hand. All paths through `ProjectLayout`. (MBSE B1 fix.)
- T10.6 — Integration test: `--validate-spec` passes against fixture series spec → `--init-book` generates scene inventory → `--job` for scene 1.1 generates FINAL output → `--verify-book` reports compliance.

**Acceptance.** Full pipeline integration test passes (T10.6). BookStructuralVerifier correctly fails fixture with missing heat_curve. Spec validator correctly rejects sentinel strings. `make test` passes.

**References.** Manus-agnostic: `orchestrator.py`, `book_structure_planner.py`, `book_structural_verifier.py`. MBSE: `Reviewer Response §5`, `Reviewer Response §3 (B1, B4, B5)`.

---

## Phase 11 — Control + Collaboration Layer

**Goal.** Paperclip (control plane), WUPHF (collaboration + series bible), ROMA (recursive decomposition) integrated into the pipeline.

**Source.** Bunko (`BUNKO-ARCH-001-v0.2.md §2, §12, §13`). All three confirmed real open-source tools.

**Tasks.**
- T11.1 — Paperclip: model each series as a "company." Set monthly token/dollar budgets per agent role. Configure heartbeat schedule (pipeline health check). Wire approval gates: spec sign-off before `--init-book`; manuscript sign-off before `--book-publish`.
- T11.2 — WUPHF: create series workspace with: `series-bible` wiki (git-backed markdown; character cards, world facts, voice profile), `pipeline` channel (production rooms: one per book), `drafts` channel (agent drafts), activity stream (audit log of all agent actions).
- T11.3 — WUPHF → git sync: BibleSteward commits deltas to WUPHF wiki (via git). Series spec is the source of truth in WUPHF wiki.
- T11.4 — ROMA integration: use ROMA's Atomizer/Planner/Executor/Aggregator/Verifier for recursive task decomposition (series → book → act → chapter → scene planning). ROMA drives the planning phase; LangGraph manages per-scene execution state.
- T11.5 — `pipeline/control/paperclip_client.py` — Paperclip API wrapper: check_budget(), record_cost(), request_approval(), heartbeat().
- T11.6 — `pipeline/control/wuphf_client.py` — WUPHF API wrapper: post_to_channel(), update_wiki(), read_wiki(), get_activity_stream().
- T11.7 — Integration test: ROMA decomposes a fixture series into a book plan. Paperclip records agent costs. WUPHF receives a wiki update.

**Acceptance.** ROMA correctly decomposes a series spec into a scene inventory. Paperclip records costs and budget check passes. WUPHF wiki update reflected in git. Pipeline pauses if Paperclip budget exceeded. `make test` passes.

**References.** Bunko `BUNKO-ARCH-001-v0.2.md §2, §10–13`. `github.com/paperclipai/paperclip`, `github.com/nex-crm/wuphf`, `github.com/sentient-agi/ROMA`.

---

## Phase 12 — Skill Evolution (EvoSkill)

**Goal.** EvoSkill integrated for per-series skill learning from production traces.

**Source.** Bunko (`BUNKO-ARCH-001-v0.2.md §5.5, §11.8`). `sentient-agi/EvoSkill`.

**Tasks.**
- T12.1 — EvoSkill fiction-domain adaptation: redefine "failure trace" = any scene where a downstream critic scores below threshold OR QualityAgent routes to REVISE/RE-PLAN. "Success trace" = scenes that passed without REVISE.
- T12.2 — Per-series namespace in EvoSkill's git-branch versioning: `series/{series_id}/skills/`.
- T12.3 — `pipeline/evoskill/trace_collector.py` — collects scene traces (agent inputs, outputs, routing decisions, quality scores) and formats them for EvoSkill Proposer.
- T12.4 — Nightly EvoSkill pass (Prefect or cron): Proposer analyzes failure traces, classifies error mode, proposes new skill. Evaluator benchmarks on fixture corpus. Frontier Pareto-keeps best variants.
- T12.5 — Skill promotion to WUPHF wiki: approved skills are promoted to the `series-bible` wiki as editorial guidelines.
- T12.6 — Claude Managed Agents "Dreaming" feature: if it reaches GA, wire it as an alternative to EvoSkill's nightly pass. Evaluate overlap; keep whichever produces better per-series improvements.
- T12.7 — Integration test: inject a fixture failure trace, verify EvoSkill Proposer generates a candidate skill. Verify Frontier keeps it (mock Evaluator with pass).

**Acceptance.** EvoSkill processes a fiction failure trace without errors. Skill promotion to WUPHF wiki succeeds. Per-series namespace is isolated. `make test` passes.

**References.** Bunko `BUNKO-ARCH-001-v0.2.md §5.5`. `github.com/sentient-agi/EvoSkill`. `arxiv.org/abs/2603.02766`.

---

## Phase 13 — Author Dashboard

**Goal.** Live monitoring + historical browse for the author. FastAPI backend + React frontend extending the manus-agnostic TSX shell.

**Priority order (from user directive 2026-05-15):**
1. **Agent-information delivery first.** `LedgerManager.get_dashboard_summary()` must be fully wired into every scene's context pack before any frontend work begins. Agents need this data; the UI is secondary.
2. **Backend API + data model second.** All endpoints and per-character metrics in the data layer before building components.
3. **Frontend aesthetics last.** TSX component styling/design is TBD — user may provide designs or a UI design prompt will be generated. Match and extend the manus-agnostic TSX shell's existing conventions until a design direction is confirmed.

**Source.** User requirement 2026-05-15. Manus-agnostic (~21 TSX/TS files: Pipeline*, App, Admin, Series, SeriesBible, ARC, ActsView, BooksView, ChaptersView, etc.). MBSE `Book Organizer: Graphical Interface Specification.md`.

**Tasks.**
- T13.0 — **Prerequisite (do first):** Verify `LedgerManager.get_dashboard_summary()` is injected into every scene's context pack (Phase 3/6 deliverable). This is the data pipeline that makes agent-aware writing possible. Dashboard UI is blocked on this.
- T13.1 — `api/main.py` — FastAPI app. Endpoints:
  - `GET /runs/{run_id}/status` — current pipeline state (active scene, current agent, routing decisions)
  - `GET /runs/{run_id}/stream` — SSE endpoint for live updates
  - `GET /books/{book_id}/ledgers` — all 10 ledger states for a completed/active book
  - `GET /books/{book_id}/metrics/history?granularity={chapter|scene|beat}` — metric trajectory at configurable granularity (chapter, scene, or beat level)
  - `GET /books/{book_id}/metrics/history?granularity=chapter&metric=interiority_pct` — single-metric trajectory at configurable granularity + optional metric filter
  - `GET /books/{book_id}/characters/{char_id}/metrics` — per-character dialogue metrics history
  - `GET /series/{series_id}/promises` — Series Promise Ledger
  - `GET /series/{series_id}/evoskill` — accumulated skill library
  - `GET /books/{book_id}/quality_gates` — scene-by-scene quality gate decision history
- T13.2 — **Per-character dialogue metrics** — extend `BookMetricsLedger` event schema to include a `character_metrics` map: `{char_id: {sentence_length_avg, vocabulary_register_score, contraction_rate, dialogue_word_count, unique_vocabulary_size, dialogue_density_pct}}`. Computed deterministically per scene from scene text. Enables: "how does Character A differ from Character B in the way they're written?" These are included in `get_dashboard_summary()`.
- T13.3 — Extend manus-agnostic React shell: update existing TSX components to consume the FastAPI endpoints.
- T13.4 — **Live View** components:
  - `RunMonitor.tsx` — current run status: agent, scene, routing decision, cost vs budget
  - `LedgerDashboard.tsx` — all 10 ledger states with targets and budget remaining; visual dials/bars
  - `QualityFeed.tsx` — live stream of quality gate decisions as they arrive (SSE)
- T13.5 — **Historical View** components:
  - `MetricPlotter.tsx` — **configurable metric plot**: any metric (interiority_pct, sensory_density, heat_curve, dialogue_ratio, exposition_pct, etc.) at user-selected granularity (chapter / scene / beat). Granularity selector + metric selector dropdowns. Single component powers all metric charts.
  - `CharacterVoiceChart.tsx` — per-character dialogue metric comparison: sentence length, vocabulary register, contraction rate, dialogue density per character. Shows how each character's writing voice differs across the book.
  - `PromiseLedger.tsx` — all promises: open, resolved, overdue; timeline view
  - `IntimacyTimeline.tsx` — character pair intimacy escalation map
  - `SeriesTimeline.tsx` — cross-book series promise and arc tracker
  - `VoiceCalibration.tsx` — voice profile calibration history across books
  - `SkillLibrary.tsx` — EvoSkill accumulated patterns per series
- T13.6 — `Makefile` `dashboard` target: `cd dashboard && npm run dev` (dev server).
- T13.7 — `make dashboard` starts the FastAPI backend + React dev server. Dashboard accessible at localhost.
- T13.8 — **Dashboard design (deferred):** Before final styling, either (a) user provides design specs/mockups, or (b) generate a Claude UI design prompt using the component inventory and manus-agnostic TSX conventions as the brief. Aesthetics are not a blocking concern for Phase 13 completion.

**Acceptance.** `LedgerManager.get_dashboard_summary()` injects correctly into a fixture scene context pack (T13.0). `make dashboard` starts without errors. Live view shows real-time updates during smoke-test run (SSE). Historical view queries all 10 ledger states for a fixture book. `MetricPlotter.tsx` renders the same metric correctly at chapter, scene, and beat granularity. `CharacterVoiceChart.tsx` shows distinct profiles for ≥2 fixture characters.

**References.** Manus-agnostic: TSX files (ActsView, BooksView, ChaptersView, etc.). MBSE: `Book Organizer: Graphical Interface Specification.md`. User decisions 2026-05-15 (configurable plotting, character dialogue metrics, agent-information delivery priority).

---

## Phase 14 — Production Hardening + Model Promotion

**Goal.** DeepEval CI quality gates. LangGraph checkpoint persistence. Integration tests. First production-tier run.

**Source.** Research findings (DeepEval, LangGraph checkpointing). Starter (smoke test pass criteria).

**Tasks.**
- T14.1 — `tests/eval/voice_consistency_metric.py` — DeepEval custom metric: `VoiceConsistencyMetric` backed by Claude scoring generated prose against the voice profile. Threshold: configurable per genre.
- T14.2 — `tests/eval/ai_tell_metric.py` — DeepEval metric: AI-tell density per 1K words against catalog. Uses structural_analysis.py (deterministic) + optional LLM-as-judge for severity-5 tells.
- T14.3 — DeepEval CI integration: `make eval` runs both metrics against the last completed scene. Add to pre-commit hook (optional; can be noisy — user configures).
- T14.4 — LangGraph checkpoint persistence: configure SQLite checkpoint store. Test: pause run mid-scene, kill process, restart from checkpoint — scene continues without re-running completed agents.
- T14.5 — Mem0 integration: seed voice profile + accumulated character facts into Mem0 at series init. Agents retrieve relevant facts via semantic search instead of injecting entire bible into context.
- T14.6 — Claude Files API integration: upload series bible (WUPHF wiki export), voice profile, character sheets once per series init. Agents reference by file_id.
- T14.7 — Full integration test: end-to-end run of 3 scenes from a fixture Romance Module spec, using test-tier models, all 10 ledgers updated, Bible Steward active, Convergence Controller routing correctly.
- T14.8 — **Model tier promotion:** set `model_tier = production`. Run the 3-scene integration test with production models (Sonnet drafter, Opus critics). Compare prose quality vs test-tier run. Log differences.

**Smoke test pass criteria (from plan §"Smoke-test pass criteria"):** One agent accepts a spec input, calls the LLM, and returns structured output matching the agreed schema, without errors, in under 60 seconds, for at least one canned sample prompt. A full 3-scene run under 5 minutes (test tier). Anything weaker is a partial pass.

**Acceptance.** 3-scene integration test passes (test tier, then production tier). LangGraph checkpoint resume works. VoiceConsistencyMetric produces a score (threshold tunable). CI passes on a clean checkout. `make test && make eval` passes.

**References.** DeepEval `github.com/confident-ai/deepeval`. Starter `README.md §Hard constraints`. MBSE `BASELINE_REPORT.md` (smoke test precedent).

---

## Phase 15 — V2 Roadmap (Deferred)

These are deferred to V2 after V1 is producing publishable books. Do not implement in V1.

- **Ensemble drafting** (Drafter A/B/C/D: multi-model): Bunko §4. Requires vLLM + Drafter D fine-tuning.
- **Drafter D fine-tuning** (Unsloth Phase 1 SFT → Axolotl Phase 2 DPO): Bunko §6. Requires calibration corpus from V1 runs.
- **Reception tier** (reader feedback loop, Scraper → Reception Analyst → Reader Cohort Modeler): Bunko §11. Requires published books + reader reviews.
- **Voice Discriminator** (local Qwen 2.5 7B classifier): Bunko §5.3. Requires fine-tuning data.
- **harbor eval** (ratcheting probe suite): Bunko §5.6. Replaces DeepEval at scale.
- **Signing / watermarking** (Sigstore, MarkLLM, OML fingerprinting): Bunko §7–8. V2 when publishing.
- **Temporal** (durable execution engine): If LangGraph checkpoint persistence proves insufficient for very long runs (20+ books).
- **Additional genre modules**: Literary fiction, science fiction, fantasy, mystery. Each requires a working author for validation.
- **EvoSkill → Claude Dreaming handoff**: If Dreaming reaches GA and outperforms EvoSkill for fiction traces.

---

## Approval gate — End of Phase 4 (this document)

Per the plan's approval gate 5: Present this `IMPLEMENTATION_PLAN.md` for user approval before implementation begins. On approval, Phase 1 starts. Any scope changes after this are a baseline change request.

Phase 4 **APPROVED** 2026-05-15.

---

## Baseline Change Request — 2026-05-15 — booknlp-character-metrics

**Status:** APPROVED 2026-05-15

**What the plan currently says:**
- `BookMetricsLedger.character_metrics` tracks sentence_length_avg, vocabulary_register_score, contraction_rate, dialogue_word_count, unique_vocabulary_size, dialogue_density_pct.
- No explicit speaker attribution tool in the Adopt list.

**What this changes:**
1. Replace the 6-field character_metrics with a research-validated 12-field schema:
   `mtld`, `avg_word_length_chars`, `question_rate`, `exclamatory_rate`, `imperative_rate`,
   `first_person_pronoun_rate`, `second_person_pronoun_rate`, `modal_verb_rate`,
   `sentiment_mean`, `sentiment_std`, `fk_grade`, `function_word_vector`.
2. Add **BookNLP** (`booknlp`) to V1 Adopt — speaker attribution prerequisite for all per-character metrics.
3. Add to V1 Adopt: `spaCy`, `NLTK`, `lexicalrichness`, `textstat`, `vaderSentiment`, `faststylometry`.
4. Update T1.10 install command accordingly.
5. Update `book_metrics_ledger.schema.json`.

**Why:** All 12 metrics are deterministically computable with no LLM calls. Research basis: ACL 2017 "Stylome Classification on Literary Characters", ACL 2019 "Are Fictional Voices Distinguishable?", ACM DIS 2023 Portrayal system, DH Conferences War and Peace character-differentiation study. The function_word_vector (Burrows' Delta) is the most validated single method in computational stylometry. User approved 2026-05-15 after research presentation.

**Impact on later phases:** Phase 8 gains a T8.x task for BookNLP speaker attribution integration. Phase 13 `CharacterVoiceChart.tsx` uses function_word_vector pairwise delta-distance. No earlier phases affected.

**Prior approval gates:** No re-run needed — net new additions, no removals.
# Baseline Change Request — 2026-05-22 — claude-dreaming-mem0

**BCR ID:** BCR-20260522-claude-dreaming-mem0  
**Status:** DRAFT → awaiting user approval  
**Submitted:** 2026-05-22  
**Scope:** Phase 1 task additions; Phase 14 task reordering

---

## What the plan currently says

**Phase 1 (T1.1–T1.11):**
- T1.10 includes mem0ai in install command
- T1.11 ends with Paperclip/WUPHF setup
- No Claude Managed Agents configuration
- No Mem0 wiring or semantic retrieval testing

**Phase 14 (T14.5):**
- Mem0 integration deferred to Phase 14
- First wiring at production hardening stage

**EvoSkill (Phase 12):**
- EvoSkill is the sole self-improvement mechanism
- No comparison with Claude Dreaming
- No decision gate for choosing between approaches

---

## What this changes

### A. Phase 1 additions (4 new tasks)

**T1.12 — Claude Managed Agents foundation**
- Create `pipeline/core/managed_agent_config.py`
- Add `managed_agent_mode: bool` and `persistent_memory_path: str` to AgentContext
- Wire Claude API client to support:
  - Persistent memory (filesystem-backed notes)
  - Files API preparation (hooks for Phase 6)
  - Message Batches API support (hooks for Phase 14)
- Fixture test: AgentContext instantiates with managed_agent_mode=True/False
- No Dreaming evaluation yet — just infrastructure

**T1.13 — Mem0 semantic retrieval (moved from Phase 14 T14.5)**
- Install mem0ai (already in T1.10)
- Create `pipeline/core/bible_semantic_store.py` wrapper
- Wire ContextPackBuilder stub method: `get_bible_context_semantic(query: str, top_k: int = 5)`
- Seed fixture bible facts (3 characters, 2 locations)
- Test: query "Sarah's occupation" → returns top-5 relevant facts
- Document retrieval accuracy vs full-bible injection token savings

**T1.14 — Dreaming evaluation fixture**
- Create `tests/fixtures/dreaming_eval/`
- 3-scene Romance Module fixture spec (meet-cute → first-date → first-conflict)
- Smoke test runner with `--with-dreaming` and `--without-dreaming` flags
- No agent implementation yet (Phase 7) — just test harness
- Acceptance: harness runs without errors (agents not wired yet)

**T1.15 — Decision gate documentation**
- Create `docs/bcr-decisions/dreaming-vs-evoskill.md` template
- Criteria: convergence speed, prose quality (VoiceConsistencyMetric), routing decision count
- Gate location: after Phase 7 smoke test (first real agent execution)
- Outcomes: (1) Dreaming only, (2) EvoSkill only, (3) Both (Dreaming real-time + EvoSkill nightly)

### B. Phase 6 updates

**T6.1 (updated) — AgentContext includes managed agent config**
```python
AgentContext(
    project_layout,
    spec_loader,
    ledger_manager,
    log_path,
    output_dir,
    model_tier,
    managed_agent_mode=False,      # NEW
    persistent_memory_path=None    # NEW
)
```

**T6.4 (updated) — ContextManager integrates Mem0**
- Extends 3-tier context with semantic retrieval option
- `ContextManager.get_bible_context()` routes to:
  - Full injection (Phase 1–5 behavior)
  - Semantic retrieval via Mem0 (Phase 6+)

### C. Phase 7 updates

**T7.1 (updated) — WriterAgent Dreaming evaluation**
- After smoke test passes, run T1.14 fixture WITH and WITHOUT Dreaming
- Log: token usage, draft quality, revision count, routing decisions
- Record in `memory/decisions.md` as DEC-007-001

**T7.9 (updated acceptance) — Smoke test includes Dreaming path**
- Original acceptance criteria +
- Both `--with-dreaming` and `--without-dreaming` paths complete
- Token usage logged for comparison

### D. Phase 14 updates

**T14.5 — REMOVED** (moved to Phase 1 T1.13)

**T14.8 (updated) — Model tier promotion includes Dreaming status**
- Production tier switch includes: model versions + Dreaming enabled/disabled
- Reproducibility pin: `managed_agent_mode` in run manifest

---

## Why

### Strategic rationale

1. **Claude Dreaming is now available** (GA as of this session context)
   - No longer "research preview" — it's production-ready
   - Zero infrastructure burden vs EvoSkill's Proposer/Evaluator/Frontier
   - Built into Claude API — no separate scheduling

2. **Mem0 solves a known Phase 14 problem earlier**
   - Bible injection context bloat is predictable
   - By book 3, bible could be 50K+ tokens per scene
   - Semantic retrieval (top-5 facts) vs full injection saves 90%+ tokens
   - No reason to defer this — it's a deterministic win

3. **Decision gate prevents premature commitment**
   - Don't abandon EvoSkill without evidence
   - Both have theoretical merit:
     - Dreaming: real-time reflection, agent-specific learning
     - EvoSkill: meta-level pattern analysis, cross-agent synthesis
   - Outcome: keep whichever wins, or use both (complementary)

4. **Minimal Phase 1 burden**
   - T1.12: ~100 lines (config dataclass + wiring)
   - T1.13: ~150 lines (Mem0 wrapper + fixture seed)
   - T1.14: ~200 lines (test harness, no agents)
   - T1.15: documentation only
   - Total: <500 lines, no blocking dependencies

### Technical rationale

**AgentContext extension is the right place:**
- All agents already receive AgentContext
- Managed agent mode is cross-cutting (all agents benefit)
- Persistent memory path is infrastructure, not business logic

**Mem0 in Phase 1 vs Phase 14:**
- Phase 14 is "production hardening" — this is foundational architecture
- ContextManager (Phase 6) needs Mem0 wired to avoid rework
- Bible semantic store is deterministic — no research risk

**Dreaming fixture without agents is valid:**
- Test harness validates infrastructure
- Smoke test (Phase 7) is the real evaluation
- Separates "can we run with Dreaming?" from "does Dreaming help?"

---

## What stays the same

- EvoSkill Phase 12 implementation unchanged
- All 10 ledgers unchanged
- Profile system unchanged
- All schemas unchanged
- All Phase 2–5 deliverables unchanged
- Phase 1 T1.1–T1.11 acceptance criteria unchanged

---

## Impact on later phases

| Phase | Impact |
|-------|--------|
| Phase 2–5 | None (schemas/profiles independent) |
| Phase 6 | AgentContext constructor signature change (2 optional params) |
| Phase 7 | Smoke test runs twice (with/without Dreaming); decision gate |
| Phase 8–11 | None (specialist agents inherit AgentContext) |
| Phase 12 | Potential outcome: EvoSkill deferred if Dreaming wins decisively |
| Phase 13 | Dashboard may display "Dreaming enabled: Yes/No" in run metadata |
| Phase 14 | T14.5 removed (moved to Phase 1); T14.8 updated |

---

## Prior approval gates

**No re-run needed.** This is net-new scope (4 tasks) + one task move (T14.5 → T1.13).

**Rationale:**
- Phase 4 approval (2026-05-15) covered "implement the plan"
- This BCR refines Phase 1 scope before implementation starts
- No user has executed Phase 1 yet — no rework

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Dreaming evaluation inconclusive | Keep both paths working; defer decision to Phase 12 |
| Mem0 semantic retrieval poor quality | Fall back to full-bible injection; flag in DECISIONS.md |
| AgentContext signature churn | Optional params (default False/None); backward-compatible |
| Phase 1 scope creep (4 tasks) | All tasks <200 lines; total <500 lines; no external dependencies |

---

## Dependencies and prerequisites

**None blocking.** All additions use existing approved tools:
- Claude API (already in use)
- mem0ai (already in T1.10 install list)
- pytest fixtures (already in Phase 1 acceptance)

---

## Acceptance criteria (updated Phase 1)

**Original Phase 1 acceptance:**
> `make lint && make test` passes on hello-world. Pre-commit hooks fire on commit. Paperclip heartbeat green. WUPHF channel accessible.

**Updated Phase 1 acceptance:**
- Original criteria (unchanged) +
- AgentContext instantiates with `managed_agent_mode=True` without errors
- Mem0 semantic retrieval: query fixture bible → returns top-5 facts with >80% relevance
- Dreaming evaluation harness: `pytest tests/fixtures/dreaming_eval/` passes (no agents wired yet)
- `docs/bcr-decisions/dreaming-vs-evoskill.md` exists with decision criteria

---

## Baseline archive implications

**Pre-BCR baseline:** `fiction-factory-baseline-20260522-pre-bcr.tar.gz`
- Captures current IMPLEMENTATION_PLAN.md, ARCHITECTURE.md, DECISIONS.md before changes

**Post-BCR baseline:** `fiction-factory-baseline-20260522.tar.gz`
- Updated IMPLEMENTATION_PLAN.md with T1.12–T1.15
- Updated DECISIONS.md with DEC-001-001 (Dreaming evaluation gate)
- This BCR document included

---

## Review checklist

- [ ] User approves strategic rationale (Dreaming + Mem0 in Phase 1)
- [ ] User approves decision gate approach (evaluate after Phase 7)
- [ ] User approves Phase 1 scope increase (4 tasks, ~500 lines)
- [ ] User acknowledges EvoSkill may be deferred if Dreaming wins
- [ ] Baseline archive created before changes applied

---

## Approval

**Status:** APPROVED 2026-05-22

This BCR has been:
1. Appended to `IMPLEMENTATION_PLAN.md` as "Baseline Change Request — 2026-05-22"
2. Recorded in `DECISIONS.md` as DEC-001-001
3. Implemented in Phase 1 execution

**Approval signature line:**
```
APPROVED: 2026-05-22 [User]
```
