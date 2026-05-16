# Fiction-Factory Pipeline — Glossary

Canonical terminology for the Fiction-Factory pipeline. Collision resolution rule: domain-specificity → most-recent bundle → user adjudication. See `memory/glossary.md` for the full source with per-bundle citation rows.

---

## Section 1 — Core System Terms

**beat** — The smallest narrative unit: a single moment of action, decision, or revelation. Multiple beats compose a scene. *MBSE: confrontation/revelation/intimacy beat\_type; Starter: atomic unit with function + intensity + POV + expected\_reader\_response; Bunko: Outliner produces beat sheet, Atomizer may decompose further.*

**book spec / project spec** — The runtime document that fully defines a book or scene for pipeline execution. Produced by the Spec Intake Pipeline, consumed by generation agents. Every field must be schema-valid; sentinel strings are rejected on load. *MBSE: series\_spec.json / book\_spec.json / scene\_spec.json; Starter: composed result of profile resolution; Bunko: "spec" = architecture doc — see collision note in Section 5.*

**context pack** — Per-scene, per-agent JSON materialization of exactly the context each agent needs: relevant spec fields, ledger summaries, bible excerpts, voice profile, and provenance metadata. Built by ContextPackBuilder; not the same as the full project spec.

**Convergence Controller** — The autonomous routing mechanism that evaluates quality signals after each scene attempt and issues one of four decisions: GO (advance), REVISE (retry in place), RE-PLAN (restructure the scene spec), or FORCE-RESOLVE (advance under budget pressure with a logged entry). Sensitivity violations can never be FORCE-RESOLVED — they trigger RE-PLAN only. Never halts. *MBSE: Quality Gate with pass/fail/inject loop; Bunko: Editorial Critic + Beta Reader Council implied routing.*

**EvoSkill failure trace** — Fiction-domain redefinition of EvoSkill's "failure trace": any scene where a downstream critic scores below threshold, or where the Convergence Controller routes to REVISE or RE-PLAN. "Success trace" = scenes that advanced without REVISE. Used by the nightly EvoSkill pass to evolve per-series skills.

**genre module** — A profile file defining the genre contract for a book: scene-function vocabulary, required scene slots, quality gates, self-audit rubric, heat scale, structural conventions, trope library, and reader contract. Implemented as a YAML profile read by the ProfileRegistry. *Bunko: tier structure implies specialization layers; Starter: Specialization Layer on top of Universal Core.*

**genre module subtype** — The Erotica module is a subtype of the Romance Module (heat\_level = erotic, steeper heat curve, elevated sensory density targets), not a separate track. This distinction controls which profile fields are inherited vs overridden.

**heat level** — Content rating on the RWA scale (sweet / sensual / steamy / erotic), governing sex-scene presence, frequency, and explicitness. A property of the genre profile and per-scene spec. Distinct from tonal mode. *Bunko: used conflated with tonal mode — see collision note in Section 5.*

**JSON-Patch overlay** — A JSON Patch document applied by the SpecLoader to merge a genre module or specialization layer onto the Universal Core project spec. Implements the overlay architecture without branching the schema.

**ledger** — An append-only SQLite event log tracking one dimension of cumulative book state. The pipeline maintains 10 ledgers; see Section 4. The QualityAgent evaluates each scene's *contribution to running totals*, not local per-scene absolute values.

**ontology** — The formal model of all pipeline entities: structural hierarchy (Series → Book → Act → Sequence → Chapter → Scene → Beat → Paragraph → Sentence → Word), entity properties, relationships, and invariants. Defined in `core-ontology-v3.md` as Universal Core + Specialization Layers. *MBSE: hierarchical decomposition with style/rhythm/grammar as interfaces.*

**overlay** — See JSON-Patch overlay.

**pipeline** — The ordered sequence of components transforming a book specification into publishable output. At scene level: SpecValidator → WriterAgent → EditorAgent → QualityAgent → Continuity/Inject → BookStructuralVerifier → Publisher. At series level: the recursive ROMA decomposition from series → book → act → chapter → scene → beat. *MBSE: 7-step; Bunko: full recursive production sequence.*

**pipeline agent** — A specialized LLM-powered component occupying a defined role in the production pipeline: receives typed input via a context pack, produces typed output validated against a schema. Distinct from CLI agent (Claude Code). Always qualified as "pipeline agent" when the distinction matters. *MBSE: WriterAgent, EditorAgent, etc.; Starter: drafter / critic / guardian / controller; Bunko: role in tier structure.*

**profile** — An authored YAML configuration file defining values for one axis of variation (Author, Genre, Audience, Goal, Sensitivity). Profiles are composed by the ProfileRegistry into a ProjectSpec. Conflicts resolved by precedence: Constraint > Sensitivity > Goal > Genre > Audience > Author > Universal.

**provenance.json** — The metadata block inside every context pack: source\_file\_hashes, view\_schema\_version, generated\_at, agent\_id. Enables reproducibility auditing.

**scene** — A narrative unit containing beats, with POV character, goal, conflict, outcome, and lifecycle states. Lifecycle: Unspecced → Specced → DirtyDraft → NeedsReview → Approved → Final. *MBSE: 6-state lifecycle; Starter: goal + conflict + outcome + state delta + beats; Bunko: Atomizer can further decompose.*

**sensitivity profile** — The content domain policy profile. Its thresholds are sacred: the Goal profile cannot loosen them, and Sensitivity violations cannot be FORCE-RESOLVED by the Convergence Controller — they trigger RE-PLAN.

**series** — A collection of books sharing characters, world, and narrative arc; the primary production unit. In Bunko, one pipeline instance = one series, with its own voice profile. At the top of the structural hierarchy. *MBSE: Series spec → Book → Act → … hierarchy; Starter: deployment context with Series Position auxiliary axis.*

**SpecLoader** — The component that loads a spec YAML/JSON, validates it against the JSON Schema, applies overlays, and rejects sentinel strings. No agent receives a spec that has not passed through the SpecLoader.

**tonal mode** — The emotional register of a scene (tender, comedic, dark, tense, introspective, etc.). A property of scene-level spec; distinct from heat level. *Bunko: originally conflated with heat level — see collision note in Section 5.*

**track** — One of the two per-track genre adapters in the synthesis: (1) commercial/series track (Romance, Erotica, Thriller), (2) formal/literary track. Each track has its own genre module schema conventions and quality gate rubrics.

**voice profile** — Codified representation of an author's prose signature as measurable, enforceable dimensions: sentence metrics, lexical, syntactic, dialogue, sensory, pacing, metaphor, subtext, cadence, forbidden constructions, and enforcement weights. Measured on output only — no external prose is retained. Implemented as a YAML profile consumed by VoiceProfile in the agent foundation.

---

## Section 2 — Agent Roles Glossary

**BibleSteward** — Manages the continuity model / series bible. Operations: propose\_delta, validate\_delta (rejects contradictions: type-mismatch, timeline-violation, spatial, capability, voice, taboo), commit\_delta (atomic write with content-hash chain), query. Bible contradiction → RE-PLAN.

**BookStructurePlanner** — Book-level agent. Reads series + book spec and generates a full scene inventory: act/chapter/scene assignments, word targets, heat level per scene from the heat\_curve.

**BookStructuralVerifier** — Book-level agent. Checks completed manuscript against spec: word count, act proportions, scene count, heat\_curve compliance, HEA/HFN (Romance), sex\_scene frequency (Erotica), RTM requirements. Runs after all scenes are Final.

**CharacterAgent** — Specialist agent. Maintains character arc consistency and tracks wound/belief states across scenes.

**ContinuityAgent** — Specialist agent. Cross-checks each scene against the Bible before commit; surfaces contradictions to the BibleSteward.

**DialogueAgent** — Specialist agent. Line-level pass focused on dialogue authenticity, voice differentiation, and subtext.

**EditorAgent** — Line editing pass after WriterAgent. Integrates with VoiceProfile to catch forbidden constructions and enforce prose signature.

**LoopTracker** — Cross-scene continuity tracker. Enforces Promise Ledger deadlines: no chapter ships with an overdue promise. Tracks series threads in the Series Promise Ledger for cross-book arcs.

**PacingAgent** — Specialist agent. Evaluates scene rhythm against the Scene Rhythm Ledger rolling window and heat\_curve position.

**PlotAgent** — Specialist agent. Verifies plot mechanics, cause-and-effect chains, and trope commitment fulfilment.

**QualityAgent** — Quality gate agent. Evaluates each scene's contribution to running BookMetricsLedger totals (not local absolute values) and routes to the Convergence Controller. Fail-closed: any evaluator exception → needs\_review, never silent pass.

**SensoryAgent** — Specialist agent. Audits sensory density per 1K words against the target in the book spec and genre profile.

**StyleAgent** — Specialist agent. Enforces voice profile axes across the full scene; catches AI-tell catalog patterns.

**TensionAgent** — Specialist agent. Tracks narrative tension arc and flags scenes that break expected escalation sequences.

**ThemeAgent** — Specialist agent. Checks thematic coherence and trope commitment consistency across scenes.

**VoiceExemplarManager** — Exemplar pool manager (Dr. Smith spec). Provides 2 exemplars per agent call, 200–400w window, 3-tier source hierarchy with uniform random rotation and beat-type stratification. Hard invariant: auto-adding generated content raises an error. Collapse detector prevents exemplar homogenization.

**WriterAgent** — Scene drafting agent. Primary LLM call per scene; receives a fully materialized context pack. Produces a DirtyDraft that enters the scene lifecycle.

---

## Section 3 — Control Stack Terms

**DeepEval** — CI quality evaluation framework. Used for `VoiceConsistencyMetric` (LLM-as-judge against voice profile) and `AiTellMetric` (density of AI-tell catalog patterns per 1K words). Runs in `make eval`; supports regression detection after model changes.

**EvoSkill** — Skill evolution layer from production traces. Per-series namespace in git-branch versioning (`series/{series_id}/skills/`). Nightly pass: Proposer analyzes failure traces → classifies error mode → proposes candidate skill → Evaluator benchmarks → Frontier Pareto-keeps best variants. Approved skills promoted to WUPHF wiki as editorial guidelines. May be superseded by Claude Managed Agents "Dreaming" if that feature reaches GA.

**Instructor** — Pydantic + Anthropic wrapper. Every Claude call in the pipeline goes through Instructor for schema enforcement and automatic validation-retry. Eliminates the class of schema-compliance bugs.

**LangGraph** — Scene lifecycle state machine. Manages transitions through the 6 scene states (Unspecced → Final) as graph nodes with guard conditions. Provides built-in SQLite checkpointing for pause/resume.

**Mem0** — Semantic memory retrieval layer. Self-hosted, local MCP mode. Used for: voice profile accumulated state, character facts between sessions, world-bible retrieval by semantic search. Works alongside Claude Managed Agents persistent memory — Mem0 for semantic retrieval, CMA for structured session notes.

**ModelRouter** — Multi-provider LLM routing with model tiering. Test tier: Haiku 4.5, gpt-4.1-mini, Ollama phi3.5 (all LLM calls during development). Production tier: Sonnet 4.6 (drafter), Opus 4.7 (nuanced critics), Haiku 4.5 (mechanical critics). Routes through Instructor on every call.

**Paperclip** — Control plane. Models each fiction series as a "company." Provides: monthly token/dollar budget caps per agent role, approval workflows (pause/resume/terminate), immutable audit ledger, heartbeat scheduling. Self-hosted (Docker). Pipeline pauses if budget is exceeded.

**ROMA** — Recursive Atomizer / Planner / Executor / Aggregator / Verifier loop (`sentient-agi/ROMA`). Used as the recursive decomposition reasoning layer: series → book → act → chapter → scene → beat planning. LangGraph is the state machine layer; ROMA is the reasoning layer.

**WUPHF** — Collaboration plane (`nex-crm/wuphf`). Git-backed wiki (series bible, character cards, world facts), agent notebooks (private working memory), channels (production rooms, drafts), activity stream (audit log of agent actions). BibleSteward commits deltas to WUPHF wiki via git. Single Go binary, self-hosted.

---

## Section 4 — Ledger Glossary

All ledgers are append-only SQLite event logs. The QualityAgent evaluates contribution to running totals, not per-scene absolute values.

**BookMetricsLedger** — Per-scene prose metrics: interiority\_pct, sensory\_density, em\_dash\_density, dialogue\_ratio, heat\_curve\_position, ai\_tell\_count, no\_fly\_violations, sex\_scene\_count\_running, sentence\_length\_avg, exposition\_pct, action\_pct, word\_count. The primary running-total ledger.

**CharacterArcLedger** — Per-character arc events: arc\_position (opening / wound\_open / processing / wound\_healing / resolved), wound\_state, core\_belief\_current, core\_belief\_true, relationship\_states.

**IntimacyEscalationLedger** — Per character-pair escalation events: act\_type (first\_touch / first\_charged\_moment / first\_kiss / first\_explicit / escalation\_peak), heat\_level, chapter, scene.

**PromiseLedger** — Append-only record of narrative commitments (foreshadowing, Chekhov objects, character questions, mystery threads, emotional debts, thematic setups, romantic tension, world questions). No chapter ships with an overdue promise; enforced by LoopTracker.

**ReaderInformationStateLedger** — Revelation events: what the reader knows vs what characters know, irony type (dramatic / tragic / situational / none).

**SceneRhythmLedger** — Rolling window of the last 10 scene types; maintained in LedgerManager state. No separate schema — used by PacingAgent to detect monotony.

**SeriesPromiseLedger** — Cross-book promise events: promise\_id, opened\_book, must\_resolve\_by\_book, resolution\_status. Enforced by LoopTracker across series continuations.

**SubplotLedger** — Subplot events: type (romantic / professional / family / external), opened\_at, target\_resolution\_chapter, status (open / escalating / complicating / resolved).

**TropeCommitmentLedger** — Trope events per genre module: required beats with target chapters and fulfilment status (pending / fulfilled / overdue).

**Bible / ContinuityTracker** — Canonical world-state record managed by BibleSteward: Character, Location, Object, Concept, Faction, Timeline entities. Checked before each scene commit to prevent contradictions. Backed by WUPHF wiki (git). *MBSE: continuity tracker markdown + series arc tracker; Starter: Bible with propose/validate/commit/query operations.*

---

## Section 5 — Collision Resolution Record

These are the terms where bundles used different words for the same concept, or the same word for different concepts. Canonical choice and rationale are recorded here.

| Collision | Bundles | Resolution | Rationale |
|---|---|---|---|
| **"agent"** — dual meaning | MBSE + Bunko: production pipeline component (WriterAgent, etc.). Starter: also the CLI tool (Claude Code), distinguished internally as drafter/critic/controller but still called "agent." | **pipeline agent** for production roles; **CLI agent** for Claude Code. Always qualify when context is ambiguous. | Two distinct concepts at different abstraction levels; qualification prevents runtime confusion and code naming conflicts. No user vote needed — distinction is internal to the synthesis. |
| **"ARC reader"** — two referents | MBSE: LLM persona simulating advance-reader-copy (ARC) feedback; `arc_reader_personas.md`. Starter + Bunko: "arc" = narrative arc only; no ARC reader persona concept. | **ARC reader persona** for the MBSE LLM critic concept; **narrative arc** for the structural storytelling concept. | Different referents, not a true synonym collision. MBSE-specific concept retained with a qualifying noun. |
| **"spec"** — three meanings | MBSE: JSON runtime document (series\_spec.json, book\_spec.json, etc.). Starter: composed profile-resolution result (Project Spec). Bunko: architecture specification document. | **book spec** / **project spec** for the runtime pipeline input (MBSE + Starter agree conceptually); **architecture doc** for design/planning documents (Bunko usage). | MBSE and Starter are aligned on the core concept; Bunko used "spec" for a wholly different artifact. Qualifying "book" or "project" disambiguates at a glance. |
| **"heat level" vs "tonal mode"** — conflated in Bunko | Bunko: used both as a single compound concept. MBSE + Starter: implicit separation (heat scale in genre profile, tonal descriptors in scene spec). | **heat level** = content rating (RWA scale: sweet / sensual / steamy / erotic). **Tonal mode** = emotional register (tender / comedic / dark / tense / introspective). | Two orthogonal axes: a scene can be erotic-and-comedic or sweet-and-dark. Conflating them would corrupt the heat\_curve logic and Sensitivity profile enforcement. Domain-specificity rule favours the split. |
