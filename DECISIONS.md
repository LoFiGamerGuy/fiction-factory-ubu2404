# DECISIONS.md — Autonomous Fiction Pipeline

**This file is append-only. New decisions go at the top of each section (most-recent first).**

Authoritative ledger: `memory/decisions.md`. This file provides a reference-format view of all binding decisions.
Format per entry: ID · Date adopted · Statement · Rationale · Supersedes (if any).

---

## Section 1: Pre-Implementation Standing Decisions (DEC-000-*)

These 11 decisions are non-negotiable for all V1 implementation. Source: `IMPLEMENTATION_PLAN.md §"Pre-implementation standing decisions"` + Starter DEC-000-1 through DEC-000-7.

---

### DEC-000-11 — Author Dashboard as Phase 13 Deliverable
**Date:** 2026-05-15
**Statement:** The Author Dashboard is a first-class Phase 13 deliverable: live monitoring + historical browse, FastAPI backend + React frontend extending the manus-agnostic TSX shell.
**Rationale:** Author insight into running pipeline state and book history is a core product requirement, not an afterthought. The manus-agnostic TSX shell (~21 files) is the starting point; the data layer is the append-only SQLite ledger system.
**Supersedes:** n/a — net new scope item.

---

### DEC-000-10 — BookMetricsLedger + 9 Additional Ledgers (Running-Total Model)
**Date:** 2026-05-15
**Statement:** All 10 ledgers track running cumulative state (not per-scene averages). QualityAgent evaluates a scene's contribution to the running total, not its local absolute value.
**Rationale:** Per-scene average enforcement misses book-level drift. A high-interiority scene should pass if the running total is below target. Detects pacing failure by chapter 10, not post-production.
**Supersedes:** Any implicit per-scene-average quality gate pattern.

---

### DEC-000-9 — Model Tiering
**Date:** 2026-05-15
**Statement:** Use `model_tier = test` (Haiku 4.5 / gpt-4.1-mini / Ollama phi3.5) for all LLM calls during development. Promote to `production` tier (Sonnet drafter / Opus critics) only after architecture is stable (Phase 14).
**Rationale:** Saves API credits while validating architecture correctness. Prose quality is independent of pipeline wiring correctness.
**Supersedes:** n/a.

---

### DEC-000-8 — Heavier-Weight, More Robust from the Start
**Date:** 2026-05-14
**Statement:** Where two implementation paths exist, choose the more robust one. Under full-auto operation every silent-failure path becomes a manuscript-corruption path.
**Rationale:** MBSE Reviewer Response §4. Full automation amplifies fragility; robustness must be baked in from Phase 1, not retrofitted.
**Supersedes:** n/a.

---

### DEC-000-7 — Schemas Are the Contract
**Date:** 2026-05-14
**Statement:** Every component input/output validates against a schema. Schema validation failures auto-retry, then become FORCE-RESOLVE entries with logging. No silent passes.
**Rationale:** Schema-as-contract is the only reliable mechanism to catch data shape mismatches across agent boundaries in a fully autonomous pipeline.
**Supersedes:** n/a.

---

### DEC-000-6 — Reproducibility First-Class
**Date:** 2026-05-14
**Statement:** Every run pins seed, model version, profile version, and registry snapshot. Same inputs + seed = bit-identical outputs.
**Rationale:** Debugging and quality regression analysis require reproducible runs. Reproducibility is not optional in an autonomous pipeline that may run unattended.
**Supersedes:** n/a.

---

### DEC-000-5 — Sensitivity Profile Thresholds Are Sacred
**Date:** 2026-05-14
**Statement:** Sensitivity Profile thresholds cannot be loosened by the Goal profile. Sensitivity violations cannot be FORCE-RESOLVED — they trigger RE-PLAN only.
**Rationale:** Allowing the Goal to override Sensitivity would silently violate author content policy. RE-PLAN is the only safe response to a Sensitivity violation.
**Supersedes:** n/a.

---

### DEC-000-4 — No Human Gates in the Inner Generation Loop
**Date:** 2026-05-14
**Statement:** The Convergence Controller is fully autonomous. Two human gates only: spec authoring and post-run review.
**Rationale:** Human gates inside the scene generation loop defeat the purpose of an autonomous pipeline and introduce unbounded latency.
**Supersedes:** n/a.

---

### DEC-000-3 — No Prose Retention from External Sources
**Date:** 2026-05-14
**Statement:** Voice extraction = measurement only. Source prose enters, axes are computed, prose is discarded. No external prose is retained in the system.
**Rationale:** Copyright compliance and clean separation between measured voice axes and generated content.
**Supersedes:** n/a.

---

### DEC-000-2 — Conflict Precedence Order
**Date:** 2026-05-14
**Statement:** Profile conflict precedence is: Constraint > Sensitivity > Goal > Genre > Audience > Author > Universal.
**Rationale:** Provides a deterministic, auditable tie-breaking rule when multiple profiles specify conflicting values for the same field.
**Supersedes:** n/a.

---

### DEC-000-1 — V1 Primary Profile Axes
**Date:** 2026-05-14
**Statement:** The five primary profile axes for V1 are: Author × Genre × Audience × Goal × Sensitivity.
**Rationale:** Sufficient to express the full commercial fiction configuration space (including erotica/heat, thriller, literary) without over-engineering a V1 profile system.
**Supersedes:** n/a.

---

## Section 2: Synthesis Decisions (from Review)

Decisions made during Phase 2 review and Phase 3 planning. Binding for implementation.

---

### SYN-013 — Per-Character Dialogue Metrics + BookNLP
**Date:** 2026-05-15
**Statement:** BookMetricsLedger.character_metrics tracks 12 per-character deterministic metrics per scene (keyed by character_id): MTLD, avg_word_length_chars, question_rate, exclamatory_rate, imperative_rate, first_person_pronoun_rate, second_person_pronoun_rate, modal_verb_rate, sentiment_mean, sentiment_std, fk_grade, function_word_vector. BookNLP added to V1 adopt list as the speaker attribution prerequisite. Supporting libraries added: spaCy, NLTK, lexicalrichness, textstat, vaderSentiment, faststylometry.
**Rationale:** Research-validated character voice differentiation metrics; all deterministic (no LLM calls). Academic basis: ACL 2017 "Stylome Classification on Literary Characters", ACL 2019 "Are Fictional Voices Distinguishable?", DH Conferences War and Peace study, ACM DIS 2023 Portrayal system. Dashboard CharacterVoiceChart uses function_word_vector pairwise delta-distance to show how distinctly each character's voice is written.
**Supersedes:** n/a — net new addition.

---

### SYN-012 — Author Dashboard: Agent-Information Delivery First; Configurable Metric Plotting
**Date:** 2026-05-15
**Statement:** The Author Dashboard's first priority is delivering context-pack data to the author (agent-information delivery pipeline). Frontend aesthetics are secondary. The dashboard must support configurable metric plotting at chapter/scene/beat granularity, and per-character dialogue metrics.
**Rationale:** User directive 2026-05-15: "developing an actual author dashboard where I could monitor this progress as books are being written and pull up historical information." Data layer (SQLite ledger system) drives the design; the UI layer extends it.
**Supersedes:** n/a — net new scope definition.

---

### SYN-011 — Series as Primary Production Unit (Bunko Posture)
**Date:** 2026-05-15
**Statement:** The series — not the book — is the primary production unit. All pipeline configuration, EvoSkill skill namespaces, WUPHF workspaces, and Paperclip company accounts are organized at the series level.
**Rationale:** Bunko market insight: romance/erotica readers consume series, not one-off novels. Series-level continuity (character arcs, series promises, cross-book escalation) is a first-class architectural concern, not an add-on.
**Supersedes:** n/a.

---

### SYN-010 — VoiceExemplarManager Spec (Dr. Smith)
**Date:** 2026-05-15
**Statement:** VoiceExemplarManager provides 2 exemplars per call (200–400w window), 3-tier source hierarchy, uniform random rotation, beat-type stratification hook, provenance per generated scene, collapse detector, and a hard invariant: generated content must never be auto-added as an exemplar.
**Rationale:** MBSE Reviewer Response §3 (M13) and Dr. Smith Closure Note. Auto-adding generated content creates a voice-drift feedback loop. 2-exemplar window balances context budget against diversity.
**Supersedes:** Any implicit exemplar injection pattern from manus-agnostic base code.

---

### SYN-009 — Permanent Line-Editor-in-the-Loop Release Gate
**Date:** 2026-05-15
**Statement:** A human line-editor review gate is permanently in place before any manuscript is published. The Convergence Controller's inner loop is fully autonomous; the publication step requires human sign-off.
**Rationale:** Fully autonomous publication without human review is an unacceptable quality and reputational risk for a commercial fiction pipeline. The gate is implemented via Paperclip approval workflow.
**Supersedes:** n/a.

---

### SYN-008 — Erotica as Genre Module Subtype (Not a Separate Track)
**Date:** 2026-05-15
**Statement:** Erotica/high-heat is a Genre Module subtype within the commercial track — not a separate architecture track. Key parameters: `heat_level = erotic`, `interiority_budget_pct_max = 0.20`, `exposition_budget_pct_max = 0.15`, `sex_scene_frequency_min = 1_per_3_chapters`, steep `heat_curve` (first sex scene by chapter 2), escalation rule (no repeated beat type within 3 scenes).
**Rationale:** The pacing failure mode (too slow, too much interiority/exposition) is a configuration problem, not an architecture problem. Addressable via Bunko Voice Profile pacing section + MBSE heat_curve + goal_profile frequency constraints. No separate pipeline needed.
**Supersedes:** Any provisional assumption that erotica required a separate track.

---

### SYN-007 — Full Ledger Inventory: 10 Ledgers
**Date:** 2026-05-15
**Statement:** The pipeline maintains 10 ledgers: (1) BookMetricsLedger, (2) PromiseLedger, (3) Bible/ContinuityTracker, (4) Character Arc Ledger, (5) Intimacy/Escalation Ledger, (6) Reader Information State Ledger, (7) Scene Rhythm Ledger, (8) Subplot Ledger, (9) Trope Commitment Ledger, (10) Series Promise Ledger. Ledgers 4–7 are V1 priority. Ledgers 8–10 are V1 or early V2. All ledgers are append-only SQLite event logs exposed in every scene's context pack.
**Rationale:** User question 2026-05-15: "are there any other ledgers we should have available for the authors?" Each ledger tracks a distinct narrative dimension that the inner loop cannot safely ignore. The Intimacy/Escalation Ledger directly addresses the erotica pacing concern; the Character Arc Ledger is the most universally necessary missing piece.
**Supersedes:** Earlier 3-ledger assumption (PromiseLedger + BookMetricsLedger + Bible/ContinuityTracker only).

---

### SYN-006 — BookMetricsLedger: Contribution-to-Running-Total Model
**Date:** 2026-05-15
**Statement:** BookMetricsLedger tracks all deterministically-measurable stylometric metrics cumulatively after each finalized scene. QualityAgent evaluates a scene's contribution to the running total, not its local absolute value.
**Rationale:** User directive 2026-05-15: "track running metrics so the author knows where they are with respect to the entire book." The PromiseLedger pattern in Starter is the right model — extended to stylometrics. Enables early pacing detection (by chapter 10, not post-production).
**Supersedes:** Any per-scene-average quality gate approach.

---

### SYN-005 — Genre Module Architecture as Structural Pattern
**Date:** 2026-05-14
**Statement:** The Genre Module Architecture (from MBSE craft reviews) is the key structural concept for all genre-specific behavior. Genre profiles are data files; code reads them. All genre-specific logic (heat_curve, required_scene_slots, trope_library, quality_gates, scene_function_vocabulary) lives in `profiles/genre/`.
**Rationale:** Validated independently by MBSE review record and confirmed at §2.1.6 synthesis gate. Enables clean extension to new genres without code changes.
**Supersedes:** Any implicit hard-coded genre logic in manus-agnostic base code.

---

### SYN-004 — Manus-Agnostic as Implementation Foundation
**Date:** 2026-05-14
**Statement:** The manus-agnostic codebase (~85% mature, 19.5K lines, multi-provider ModelRouter, 9 specialist agents, data-driven VoiceProfile) is the primary implementation artifact. It supersedes the MBSE top-level code for implementation planning.
**Rationale:** A2 triage confirmed manus-agnostic maturity and that it resolves key MBSE bugs. MBSE top-level code is ~60% mature and has known issues (B1–B12) that manus-agnostic already addresses.
**Supersedes:** Earlier assumption that MBSE top-level code was the implementation baseline.

---

### SYN-003 — Instructor for All LLM Calls
**Date:** 2026-05-15
**Statement:** All LLM calls use Instructor (pydantic+Anthropic wrapper) for schema enforcement and automatic validation retries. Raw `response_format` dicts are not used.
**Rationale:** Instructor provides structured output enforcement with retry logic out of the box. Aligns with DEC-000-7 (schemas as contract) without boilerplate per-agent parsing code.
**Supersedes:** Any raw `response_format` dict pattern in manus-agnostic base code.

---

### SYN-002 — Overlay Architecture (SpecLoader + JSON-Patch)
**Date:** 2026-05-14
**Statement:** Series and book specs use a JSON-Patch overlay architecture (SpecLoader). Book specs overlay on series specs; no copy-on-init. Agents always read through SpecLoader, never raw YAML.
**Rationale:** Copy-on-init leads to spec divergence as series configuration evolves. Overlays keep the series spec as the single source of truth.
**Supersedes:** Any copy-on-init or flat-file-per-book spec pattern.

---

### SYN-001 — Synthesis Shape: Shared Core + Per-Track Genre Modules
**Date:** 2026-05-14 (provisional) / 2026-05-15 (binding, §2.4 locked)
**Statement:** Architecture is Shared Core + per-track Genre Modules. V1 tracks: (1) Commercial/romance-first (MBSE Romance Module + Bunko Voice Profile + manus-agnostic pipeline); (2) Series-level production loop (EvoSkill pattern accumulation, cross-book continuity); (3) Thriller/literary scaffold (v0.1 spec only, unvalidated implementation).
**Rationale:** No single bundle was a clear winner. Starter provides the Universal Core ontology; manus-agnostic provides the implementation foundation; MBSE provides the Genre Module Architecture and craft review validation; Bunko provides the Voice Profile schema and series-production posture.
**Supersedes:** Any single-bundle-wins assumption. Provisional §2.1.6 decision now binding.

---

## Section 3: Open Items / V2 Scope

Items explicitly deferred to V2. Do not implement in V1.

| Item | Source | Deferral Reason |
|---|---|---|
| **Ensemble drafting** (Drafter A/B/C/D multi-model) | Bunko §4 | Requires vLLM + Drafter D fine-tuning; needs V1 calibration corpus first. |
| **Drafter D fine-tuning** (Unsloth SFT → Axolotl DPO) | Bunko §6 | Requires V1 production traces as training data. |
| **Reception tier** (Scraper → Reception Analyst → Reader Cohort Modeler) | Bunko §11 | Requires published books + reader reviews. |
| **Voice Discriminator** (local Qwen 2.5 7B classifier) | Bunko §5.3 | Requires fine-tuning data from V1 runs. |
| **harbor eval** (ratcheting probe suite) | Bunko §5.6 | Replaces DeepEval at scale; premature before V1 corpus exists. |
| **Signing / watermarking** (Sigstore, MarkLLM, OML fingerprinting) | Bunko §7–8 | V2 when publishing; no V1 publishing pipeline yet. |
| **Temporal durable execution** | Research | LangGraph checkpoint persistence is sufficient for V1 run lengths. |
| **Additional genre modules** (literary fiction, sci-fi, fantasy, mystery) | MBSE scaffolds | Each requires a working author for validation. Thriller v0.1 scaffold is spec-only. |
| **EvoSkill → Claude Dreaming handoff** | Bunko §5 | Monitor Claude Dreaming GA; evaluate vs EvoSkill when available. |
| **Fine-tuning / cloud GPU** (AWS GPU, Sentient-Enclaves) | Bunko | Deferred; local dev only for V1. |
| **Paid scraping services** (Apify, Bright Data, Composio) | Various | Deferred; no reception tier in V1. |
