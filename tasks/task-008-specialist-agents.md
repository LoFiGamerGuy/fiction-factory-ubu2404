# Task 008 — Specialist Agents

```
status: pending
started:
completed:
phase: 8
estimated_hours: 10-14
depends_on: task-007
```

## Goal

Full editorial pipeline: all 9 specialist agents ported from manus-agnostic and integrated with AgentContext + Instructor. VoiceExemplarManager implemented per Dr. Smith's spec (2 exemplars/call, 200–400w window, collapse detector, hard invariant against auto-add of generated content). GenreNormEditor integrated with GenreModule profile.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 8 (Specialist Agents)

## Dependencies

- task-007 (WriterAgent, EditorAgent, BaseAgent pattern — all specialist agents follow same contract)
- task-005 (genre profile YAML — GenreNormEditor reads romance_module_v1.yaml for enforcement)
- task-006 (VoiceProfile — VoiceExemplarManager sources exemplars from VoiceProfile)

## Acceptance criteria

- [ ] `pipeline/agents/arc_reader_agent.py` — ported from manus-agnostic; AgentContext + Instructor; `impl_class = "llm"`
- [ ] `pipeline/agents/arc_reader_packet_agent.py` — ported; AgentContext + Instructor
- [ ] `pipeline/agents/drift_detector_agent.py` — ported; AgentContext + ContextPack integration
- [ ] `pipeline/agents/developmental_editor_agent.py` — ported; AgentContext + Instructor
- [ ] `pipeline/agents/line_editor_agent.py` — ported; AgentContext + Instructor
- [ ] `pipeline/agents/copy_editor_agent.py` — ported; AgentContext + Instructor
- [ ] `pipeline/agents/proofreader_agent.py` — ported; AgentContext + Instructor
- [ ] `pipeline/agents/genre_norm_editor_agent.py` — ported; reads genre_profile.yaml for scene-function vocabulary, required-scene enforcement, heat escalation rules
- [ ] `pipeline/agents/revision_agent.py` — ported; AgentContext + Instructor
- [ ] `pipeline/voice_exemplar_manager.py` — VoiceExemplarManager per Dr. Smith spec
- [ ] VoiceExemplarManager: exactly 2 exemplars per call
- [ ] VoiceExemplarManager: 200–400 word window per exemplar (hard bounds, not targets)
- [ ] VoiceExemplarManager: 3-tier source hierarchy (user-provided → calibration corpus → synthetic fallback)
- [ ] VoiceExemplarManager: uniform random rotation with beat-type stratification hook
- [ ] VoiceExemplarManager: provenance per generated scene (which exemplars were used, their source tier)
- [ ] VoiceExemplarManager: collapse detector — detect if rotation is collapsing to same exemplar repeatedly
- [ ] VoiceExemplarManager: hard invariant — `add_generated_content()` raises `ValueError("Cannot auto-add generated content to exemplar pool")`; test verifies this
- [ ] GenreNormEditor integration test: enforces Romance Module v1.0 heat_curve check (scene with wrong heat_level for its position in book → flagged)
- [ ] All 9 specialist agents: unit test instantiates + runs against fixture input without error
- [ ] `make test` passes

## Subtasks

- T8.1 — Port `arc_reader_agent.py` from `.workspace/manus-agnostic/`. Adaptations: (1) Constructor → `AgentContext`. (2) All LLM calls → Instructor returning typed `ArcReaderOutput`. (3) `impl_class = "llm"`. ArcReaderAgent reads the current character arc state from CharacterArcLedger (via LedgerManager) to assess arc progression.
- T8.2 — Port `arc_reader_packet_agent.py` from manus-agnostic. Same adaptations. ArcReaderPacketAgent assembles the arc analysis packet (structured summary of arc positions for all characters) for use by other agents.
- T8.3 — Port `drift_detector_agent.py` from manus-agnostic. Adaptations: AgentContext; ContextPack integration. DriftDetectorAgent: uses ContextManager's book-tier context (recent chapter summaries) to detect voice drift from VoiceProfile targets. Returns typed `DriftDetectorOutput` with drift_detected bool and axis-level drift scores.
- T8.4 — Implement `pipeline/voice_exemplar_manager.py`. `VoiceExemplarManager` class:
  - `__init__(voice_profile: VoiceProfile, exemplar_pool: list[Exemplar])`: validates pool size ≥ 3 (minimum for collapse detection).
  - `Exemplar` dataclass: `text: str` (200–400 words enforced; raise ValueError if outside range), `source_tier: str` (user_provided/calibration_corpus/synthetic_fallback), `beat_type: str | None`, `exemplar_id: str`.
  - `get_exemplars(beat_type: str | None = None, n: int = 2) → list[Exemplar]`: exactly n=2 exemplars. Apply 3-tier priority: user_provided first, then calibration_corpus, then synthetic_fallback. Uniform random rotation within tier. Beat-type stratification: if beat_type given, prefer exemplars with matching beat_type.
  - `collapse_detector: CollapseDetector`: tracks last K exemplar selections; raises `CollapseWarning` if same exemplar_id appears > 50% of last K calls.
  - `record_usage(scene_id: str, exemplars_used: list[Exemplar])`: logs provenance to per-scene provenance file.
  - `add_generated_content(text: str) → None`: raises `ValueError("Cannot auto-add generated content to exemplar pool. Exemplars must be user-provided or from calibration corpus.")`. Hard invariant — no exception catching allowed around this method in agent code.
- T8.5 — Port `developmental_editor_agent.py`, `line_editor_agent.py`, `copy_editor_agent.py`, `proofreader_agent.py` from manus-agnostic. All: AgentContext + Instructor + typed outputs. Each has distinct scope: DevelopmentalEditor = structure/arc/pacing; LineEditor = prose polish/voice; CopyEditor = grammar/style/consistency; Proofreader = final errors/typos.
- T8.6 — Port `revision_agent.py` from manus-agnostic. RevisionAgent: receives EditorOutput + revision directives from ConvergenceController (REVISE routing); generates revised draft. Returns typed `RevisionOutput`.
- T8.7 — Port `genre_norm_editor_agent.py` from manus-agnostic. GenreNormEditor integration: (1) Load genre_profile at init via `SpecLoader` (e.g., `romance_module_v1`). (2) `enforce_scene_function(scene: SceneOutput, spec: ProjectSpec) → GenreNormResult`: check scene_function against `scene_function_vocabulary`. (3) `enforce_heat_curve(scene: SceneOutput, spec: ProjectSpec, book_position: float) → bool`: check scene heat_level against heat_curve target for current book position. (4) `check_required_slots(chapter_scenes: list[SceneOutput], spec: ProjectSpec) → list[SlotViolation]`: verify required scene slots are filled.
- T8.8 — Inject VoiceExemplarManager into AgentContext: add optional `voice_exemplar_manager: VoiceExemplarManager | None = None` field to AgentContext (if not already added in Phase 6 T6.3). WriterAgent: if VoiceExemplarManager present, call `get_exemplars(beat_type)` and include in context pack.
- T8.9 — Write unit tests `tests/unit/agents/test_specialist_agents.py`: each of 9 agents instantiates with fixture AgentContext + runs against fixture input without error (use mock ModelRouter to avoid API calls in unit tests). GenreNormEditor heat_curve test: scene with heat_level=4 at book_position=0.1 (Romance v1 requires heat_level≤2 at open) → SlotViolation returned. DriftDetector test: fixture with exaggerated voice drift → drift_detected == True.
- T8.10 — Write VoiceExemplarManager tests `tests/unit/test_voice_exemplar_manager.py`: (1) Hard invariant test: `manager.add_generated_content("...")` raises ValueError. (2) Window bounds test: Exemplar with 150-word text raises ValueError at construction. (3) Exactly-2-exemplars test: `get_exemplars()` always returns exactly 2. (4) Collapse detector test: call `get_exemplars()` 10 times with pool of 2 → CollapseWarning raised.
- T8.11 — Commit: `feat(agents): 9 specialist agents + VoiceExemplarManager (task-008)`.

## Key decisions that affect this task

- **VoiceExemplarManager: 2 exemplars/call, 200–400w window, no auto-add, collapse detector (decisions.md — Dr. Smith spec):** These are hard invariants, not configurable parameters. The `add_generated_content()` ValueError is a safety property — generated prose must never contaminate the exemplar pool.
- **Every Claude call through Instructor:** All 9 specialist agents that use LLMs must return typed pydantic models. No raw text.
- **No prose retention from external sources (DEC-003):** VoiceExemplarManager's exemplar pool sources: user-provided text and calibration corpus only. No external scraped prose.
- **GenreNormEditor reads genre profile (DEC-007 / schemas are the contract):** Heat curve, scene function vocabulary, and required slots come from `genre_profile.yaml` — never hardcoded in agent code.
- **Heavier-weight from start (DEC-008):** All 9 agent constructors validate their inputs via AgentContext. Unit tests use mock ModelRouter to avoid API calls — but the contract is fully validated.

## Suggested approach

1. Port the simpler deterministic-adjacent agents first (DriftDetector, Proofreader, CopyEditor).
2. Port the LLM-heavy agents (DevelopmentalEditor, LineEditor, ArcReader, ArcReaderPacket).
3. Implement VoiceExemplarManager — write tests before implementing the collapse detector.
4. Port GenreNormEditor last (needs genre profile integration from Phase 5).
5. Wire VoiceExemplarManager into AgentContext and WriterAgent.
6. Run all tests; verify `make test` passes.
7. Commit.

## Decisions to log in DECISIONS.md

- VoiceExemplarManager collapse threshold (50% of last K calls — log K value chosen).
- Beat-type stratification implementation (prefer matching beat_type within tier).
- Provenance logging format for exemplar usage.

## Notes

- Manus-agnostic source files: `.workspace/manus-agnostic/arc_reader_agent.py`, `arc_reader_packet_agent.py`, `drift_detector_agent.py`, `developmental_editor_agent.py`, `line_editor_agent.py`, `copy_editor_agent.py`, `proofreader_agent.py`, `genre_norm_editor_agent.py`, `revision_agent.py`. Read each before porting.
- The 9 specialist agents are not all invoked on every scene. The Convergence Controller selects which specialists to invoke based on routing decisions. GenreNormEditor runs on every scene; the others run as needed.
- VoiceExemplarManager is the mechanism that keeps WriterAgent's voice consistent across a 100K-word novel. Its invariants are non-negotiable.

## Out of scope

- BibleSteward / LoopTracker (Phase 9)
- Book-level orchestration (Phase 10)
- DeepEval VoiceConsistencyMetric (Phase 14 — uses VoiceExemplarManager as input)
