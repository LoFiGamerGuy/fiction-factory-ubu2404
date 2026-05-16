# Task 006 — Agent Foundation

```
status: pending
started:
completed:
phase: 6
estimated_hours: 8-12
depends_on: task-003, task-004
```

## Goal

Core agent infrastructure: `AgentContext` dataclass, `ModelRouter` with Instructor wrapping on every Claude call, `VoiceProfile` with Bunko schema extensions, `ContextManager` with three-tier context + ledger integration, `ContextPackBuilder` with per-job materialized JSON and provenance, `BaseAgent`, `JobContext`, and `ProjectLayout`. Every subsequent agent phase inherits from this foundation.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 6 (Agent Foundation)

## Dependencies

- task-003 (LedgerManager — injected into AgentContext)
- task-004 (ProfileRegistry, SpecLoader, ProjectSpec — injected into AgentContext)

## Acceptance criteria

- [ ] `pipeline/core/agent_context.py` — `AgentContext(project_layout, spec_loader, ledger_manager, log_path, output_dir, model_tier)` dataclass; every agent constructor takes AgentContext
- [ ] `pipeline/core/model_router.py` — multi-provider routing (Anthropic / OpenAI / Ollama), model_tier switching (test/production), Instructor wrapping on every LLM call, cost logging to `data/cost_log.jsonl`
- [ ] ModelRouter test: test tier routes to claude-haiku-4-5 (Anthropic) and gpt-4.1-mini (OpenAI); production tier routes to claude-sonnet-4-6 and gpt-4.1
- [ ] ModelRouter: every call returns a structured pydantic model via Instructor — no raw text responses accepted
- [ ] `pipeline/core/voice_profile.py` — loads from `profiles/author/` YAML; extends Bunko schema's 15 sections (forbidden_constructions regex, enforcement weights, calibration_history)
- [ ] `pipeline/core/context_manager.py` — three-tier context (scene/book/series); LedgerManager integration: Author Dashboard summary injected into every scene's context
- [ ] `pipeline/core/context_pack_builder.py` — per-scene per-agent JSON materialization; provenance.json with source_file_hashes, view_schema_version, generated_at, agent_id; hash-stamped
- [ ] `pipeline/core/base_agent.py` — all agents inherit from BaseAgent; `impl_class` attribute (deterministic/llm/hybrid); `version` string; `run()` method contract; structured JSON logging per call
- [ ] `pipeline/core/job_context.py` — `JobContext` typed dataclass replacing plain dict job passing; all agents receive and return typed JobContext
- [ ] `pipeline/core/project_layout.py` — `ProjectLayout` dataclass; all path assembly goes through it; agents never construct paths by hand
- [ ] Test: AgentContext instantiation with all required fields
- [ ] Test: ModelRouter routes correctly for both tiers (mock LLM calls)
- [ ] Test: VoiceProfile loads fixture author profile and exposes expected fields
- [ ] Test: ContextManager respects scene/book/series size limits and injects Author Dashboard summary
- [ ] Test: ContextPackBuilder produces valid provenance JSON with all required fields (source_file_hashes, view_schema_version, generated_at, agent_id)
- [ ] Test: BaseAgent run() contract — raises if impl_class not declared; structured log emitted
- [ ] `make test` passes

## Subtasks

- T6.1 — Implement `pipeline/core/project_layout.py`. `ProjectLayout` dataclass: `series_root: Path`, `book_id: str`. Methods: `series_spec_path() → Path`, `book_spec_path() → Path`, `scene_output_path(chapter: int, scene: int) → Path`, `ledger_db_path(ledger_name: str) → Path`, `context_pack_path(agent_id: str, scene_id: str) → Path`, `cost_log_path() → Path`. No agent assembles a path by string concatenation — always via ProjectLayout. (MBSE B1 fix.)
- T6.2 — Implement `pipeline/core/job_context.py`. `JobContext` typed dataclass: `job_id: str`, `series_id: str`, `book_id: str`, `chapter_id: int`, `scene_id: str`, `spec: ProjectSpec`, `model_tier: str`, `seed: int`, `run_timestamp: str`, `input_hash: str`. Agents receive `JobContext` in, return `JobContext` with output appended. No plain `dict` job passing. (MBSE B3 fix.)
- T6.3 — Implement `pipeline/core/agent_context.py`. `AgentContext` dataclass: `project_layout: ProjectLayout`, `spec_loader: SpecLoader`, `ledger_manager: LedgerManager`, `log_path: Path`, `output_dir: Path`, `model_tier: str` (default "test"). Post-init validation: all fields must be non-None — raise ValueError with descriptive message if any are missing. (Heavier-weight from start — DEC-008.)
- T6.4 — Implement `pipeline/core/model_router.py`. Port from manus-agnostic `model_router.py`. Changes: (1) Load model names from `model_router.json` (no hardcoded strings). (2) Add `model_tier` switching: `route(provider: str, tier: str) → str` returns model name. (3) Wrap every call with Instructor: `call(messages, response_model: type[BaseModel], provider: str, seed: int) → BaseModel` — returns a pydantic model, never raw text. (4) Log every call to `data/cost_log.jsonl`: `{job_id, agent_id, provider, model, input_tokens, output_tokens, cost_usd, duration_ms, timestamp}`.
- T6.5 — Implement `pipeline/core/voice_profile.py`. Port from manus-agnostic `voice_profile.py`. Extensions: (1) Load all 9 axis categories from the author_profile schema (Phase 4). (2) Add Bunko schema's 15 sections: enforce `forbidden_constructions` as compiled regex list; load `enforcement_weights` dict; store `calibration_history` list. (3) `load(profile_path: Path) → VoiceProfile` validates YAML against author_profile.schema.json before returning.
- T6.6 — Implement `pipeline/core/context_manager.py`. Port from manus-agnostic `context_manager.py`. Extensions: (1) Three-tier context windows: scene-tier (last N scenes, configurable), book-tier (chapter summaries + bible snapshot), series-tier (series facts + cross-book promises). (2) LedgerManager integration: call `ledger_manager.get_dashboard_summary()` and inject `AuthorDashboard` into scene-tier context for every scene. (3) Size limit enforcement: if combined context exceeds tier limit, truncate scene-tier first, then book-tier (series-tier is non-negotiable).
- T6.7 — Implement `pipeline/core/context_pack_builder.py`. `ContextPackBuilder.build(job_context: JobContext, agent_id: str, context_manager: ContextManager) → ContextPack`. Output: per-scene per-agent JSON file at `ProjectLayout.context_pack_path(agent_id, scene_id)`. Each ContextPack JSON: `{agent_id, scene_id, job_id, generated_at, view_schema_version, context_tiers: {scene, book, series}, author_dashboard_summary, source_file_hashes: dict, provenance_hash: str}`. `provenance_hash`: SHA-256 of serialized context tiers + source hashes. Save companion `provenance.json` at same path. (MBSE Agent Views doc pattern.)
- T6.8 — Implement `pipeline/core/base_agent.py`. Port from manus-agnostic `base_agent.py`. BaseAgent abstract class: `impl_class: str` (must be one of "deterministic"/"llm"/"hybrid" — class-level attribute; raises if not declared), `version: str`, `run(job_context: JobContext) → JobContext` (abstract). On every `run()`: emit structured JSON log to `log_path`: `{component_id, version, impl_class, job_id, input_hash, output_hash, duration_ms, model_version (if llm), timestamp}`. Subclasses call `super().run()` or use `@run_logged` decorator.
- T6.9 — Write tests `tests/unit/core/test_agent_foundation.py`: AgentContext constructor validation (missing field → ValueError), ProjectLayout path assembly (no string concatenation), ModelRouter tier routing (mock anthropic + openai clients, verify model names per tier), ModelRouter Instructor wrapping (mock returns pydantic model not raw text), VoiceProfile load + forbidden_constructions compiled, ContextManager size limit enforcement + AuthorDashboard injection, ContextPackBuilder provenance JSON (all required fields present, hash matches content), BaseAgent impl_class guard (raises if not declared).
- T6.10 — Write fixture `tests/fixtures/core/fixture_job_context.json` and `tests/fixtures/core/fixture_project_layout.json` for test construction.
- T6.11 — Commit: `feat(core): agent foundation — AgentContext, ModelRouter+Instructor, VoiceProfile, ContextManager, ContextPackBuilder, BaseAgent, JobContext, ProjectLayout (task-006)`.

## Key decisions that affect this task

- **Every Claude call through Instructor (decisions.md 2026-05-15):** ModelRouter wraps every LLM call with Instructor. No raw `client.messages.create()` with manual JSON parsing anywhere in the codebase. Response must be a typed pydantic model.
- **AgentContext constructor validates (DEC-008):** All agent constructors take AgentContext. AgentContext post-init raises ValueError if any field is None. No silent construction with missing dependencies.
- **JobContext typed (DEC-008 / MBSE B3 fix):** All job passing is via typed JobContext dataclass. No plain dict threading through the pipeline.
- **ProjectLayout for all paths (MBSE B1 fix):** No agent concatenates path strings by hand. Every path goes through ProjectLayout.
- **ContextPackBuilder with provenance (MBSE Agent Views):** Per-job materialized JSON with provenance.json and hash-stamped content.
- **Model tiering (DEC-009):** ModelRouter reads tier from AgentContext.model_tier. Default = "test". Never hardcode model names.
- **VoiceExemplarManager:** 2 exemplars per call, 200–400w window, no auto-add of generated content, collapse detector required — this is implemented in Phase 8 (T8.4), not here. Phase 6 only establishes VoiceProfile.

## Suggested approach

1. Implement ProjectLayout first (simplest; everything else depends on it).
2. Implement JobContext (simple dataclass).
3. Implement AgentContext (depends on ProjectLayout, SpecLoader, LedgerManager).
4. Implement ModelRouter (most complex piece — write tests before implementing the Instructor wrapping).
5. Implement VoiceProfile (port + extend).
6. Implement ContextManager (port + extend with ledger integration).
7. Implement ContextPackBuilder (depends on ContextManager).
8. Implement BaseAgent (depends on all above).
9. Write all unit tests; verify `make test` passes.
10. Commit.

## Decisions to log in DECISIONS.md

- Instructor as the sole LLM call wrapper (no raw SDK calls).
- AgentContext constructor validation (fail-fast pattern).
- ContextPack as materialized JSON file (not in-memory only).
- Provenance hash algorithm (SHA-256 of serialized context).
- Cost logging format (JSONL at data/cost_log.jsonl).

## Notes

- Manus-agnostic `model_router.py`, `voice_profile.py`, `context_manager.py`, `base_agent.py` are the starting points. Read them before implementing. They are in `.workspace/manus-agnostic/`.
- The Instructor library wraps anthropic and openai clients. `import instructor; client = instructor.from_anthropic(anthropic.Anthropic())`. Every call: `client.chat.completions.create(response_model=SomePydanticModel, ...)`.
- Do not implement any writing/editing logic in this phase — foundation only.
- VoiceExemplarManager (Phase 8) will be injected via AgentContext later — add a nullable `voice_exemplar_manager` field to AgentContext in T6.3 with default None, so Phase 8 can populate it without changing the constructor signature.

## Out of scope

- WriterAgent, EditorAgent, QualityAgent (Phase 7)
- Specialist agents (Phase 8)
- VoiceExemplarManager (Phase 8)
- BibleSteward, LoopTracker (Phase 9)
- Paperclip/WUPHF client wrappers (Phase 11)
