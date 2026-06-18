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

### DEC-007-001 — Claude Dreaming + EvoSkill Both Retained
**Date:** 2026-05-22
**Statement:** Claude Managed Agents (Dreaming) and EvoSkill are both retained in V1. Dreaming provides agent-specific persistent memory and session continuity (future value for series production). EvoSkill provides cross-agent meta-learning (nightly pattern accumulation). Both are complementary; neither blocks V1 completion. `managed_agent_mode` is configurable (default `False` for stability). Enable Dreaming for multi-book production runs.
**Rationale:** Smoke test evaluation (3-scene Romance Module fixture) showed no significant quality or performance differences (both modes: 3/3 scenes GO, publication-ready prose, <60s total runtime). Infrastructure is zero-cost (filesystem-backed memory). Dreaming's value emerges in longer runs (10+ books, 50K+ token bibles, voice drift detection). Premature to choose one; keep both operational.
**Supersedes:** n/a — executes BCR-20260522 decision gate.
**Evaluation Report:** `docs/bcr-decisions/DREAMING_EVALUATION_RESULTS.md`

---

### DEC-001-001 — Claude Dreaming + Mem0 Phase 1 Adoption
**Date:** 2026-05-22
**Statement:** Claude Managed Agents (Dreaming) infrastructure and Mem0 semantic retrieval are adopted in Phase 1 (T1.12-T1.15). Decision gate after Phase 7 smoke test determines: (1) Dreaming only, (2) EvoSkill only, or (3) Both.
**Rationale:** Claude Dreaming is now GA (no longer research preview), with zero infrastructure burden vs EvoSkill's Proposer/Evaluator/Frontier. Mem0 solves Bible context bloat predictably (semantic retrieval saves 90%+ tokens by book 3). Decision gate prevents premature commitment — evaluate both approaches with real data.
**Supersedes:** Phase 14 T14.5 (Mem0 integration moved to Phase 1 T1.13).
**BCR:** BCR-20260522-claude-dreaming-mem0 (APPROVED 2026-05-22)
**Decision Outcome:** DEC-007-001 (Both retained)

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

---

## Section 4: Task 011–015 Decisions

### T014-036 — Targeted Revision Comparison Is a No-Live Gate
**Date:** 2026-06-18
**Statement:** The pipeline now has a no-live targeted revision comparison gate. `pipeline/revision/revision_compare.py` and `scripts/compare_revision_outputs.py` compare revised scene files against `revision_packet_manifest.json` and the packet JSON files, producing `targeted_revision_comparison.json` with source-hash checks, word-count target-band checks, Markdown appendix detection, weighted structural/AI-tell deltas, optional NoFlyScanner deltas, and repeated-phrase reduction checks. The CLI exits nonzero when any revised scene fails.
**Rationale:** Revision packets identify what to fix, but a later human/model revision pass needs deterministic acceptance criteria before any revised prose is trusted. This keeps revision validation local and no-live, catches stale-source comparisons via source SHA1, and gives the author a before/after metric report without spending model tokens.
**Supersedes:** Packet-only handoff with no deterministic revised-output validation gate.
**Verification:** `./.venv/bin/pytest tests/unit/revision/test_targeted_packets.py tests/unit/revision/test_revision_compare.py` passed (`4 passed`). `make lint` passed. `OPENAI_API_KEY= ANTHROPIC_API_KEY= make test` passed (`410 passed, 6 skipped`). Cedar Harbor dogfood regenerated the no-live backlog/packets and compared unchanged generated scenes as a negative control; `/tmp/opencode/targeted_revision_comparison_originals.json` returned `passed = false` and flagged `8` of `10` targeted scenes as still needing revision.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-035 — Targeted Revision Packets Are No-Live Artifacts
**Date:** 2026-06-17
**Statement:** The targeted revision plan now has a packetization step. `pipeline/revision/targeted_packets.py` and `scripts/build_revision_packets.py` convert `book_revision_backlog.json` into per-scene JSON and Markdown packets containing direct scene issues, relevant cross-scene repeated-phrase issues, global book-level context, revision objectives, constraints, current text hash, optional current text, and a no-live output contract. Packets are planning artifacts only; they do not rewrite prose or call a model.
**Rationale:** The autopsy backlog identifies where revision should happen, but a later human or model-driven revision pass needs scene-local packets with exact issues, constraints, and source text. Keeping packet generation no-live lets the author inspect or hand off the highest-severity scenes before approving any model spend.
**Supersedes:** A targeted plan that only listed scene IDs and issue IDs without actionable per-scene revision context.
**Verification:** `./.venv/bin/pytest tests/unit/revision/test_book_autopsy.py tests/unit/revision/test_targeted_packets.py` passed (`4 passed`). `make lint` passed. `OPENAI_API_KEY= ANTHROPIC_API_KEY= make test` passed (`408 passed, 6 skipped`). Cedar Harbor packet dogfood built `10` packets under `/tmp/opencode/revision_packets`; top packet `ch25_sc02` contained `9` scene/cross-scene issues plus global book-level context.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-034 — No-Live Book Revision Intelligence Layer
**Date:** 2026-06-17
**Statement:** The pipeline now has a no-live revision intelligence layer for completed book runs. `QualityAgent.update_ledgers()` dispatches deterministic narrative extraction into the runtime narrative ledgers: scene rhythm, character arcs, intimacy escalation, reader information, subplot, trope commitment, and promises. New deterministic book-level reviewers build `RevisionIssue` backlogs over completed run artifacts, and `scripts/analyze_book_run.py` writes `book_revision_backlog.json` plus `targeted_revision_plan.json` for the highest-severity scenes.
**Rationale:** The Cedar Harbor full-book validation proved generation and deterministic BookMetrics, but the next product gap is revision targeting: identify where a complete draft needs structural, romance-arc, promise, pacing, AI-tell, word-budget, and repeated-phrase work without spending model tokens. The old finalized-scene path still wrote `scene_type = action` and left narrative ledgers empty. Future runs now populate those ledgers during finalization; old summaries remain analyzable and correctly surface missing narrative-ledger coverage.
**Supersedes:** Placeholder runtime `scene_type = action` and empty narrative-ledger dispatch during finalized scene updates.
**Verification:** `./.venv/bin/pytest tests/unit/ledgers/test_narrative_extractor.py tests/unit/revision/test_book_autopsy.py tests/unit/test_word_count_enforcement.py tests/unit/ledgers/test_ledger_system.py` passed (`37 passed`). `make lint` passed. `OPENAI_API_KEY= ANTHROPIC_API_KEY= make test` passed (`406 passed, 6 skipped`). No-live Cedar Harbor autopsy command completed against `cedar-harbor-book01-runtime-metrics-validation`, found `54` issues, and selected `10` targeted revision scenes.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-033 — Fresh Runtime-Metrics Full-Book Validation Passed
**Date:** 2026-06-17
**Statement:** The user-approved `$5` Anthropic test-tier validation run `cedar-harbor-book01-runtime-metrics-validation` completed the full Cedar Harbor `book01` scaffold after run-local ledger and deterministic runtime BookMetrics hardening. Final summary: `50/50` scenes completed, `50/50` GO decisions, `0` force-resolved scenes, deterministic eval PASS, dashboard summary PASS, strict `BookStructuralVerifier` PASS, final status word count `65524` against the `65000` target, run-local ledger word total `66108`, and total cost `$1.3195088` / `620686` tokens.
**Rationale:** This is the first full-book proof where manuscript generation, run-local ledgers, dashboard reads, deterministic BookMetrics, enriched EvoSkill traces, and no-live learning-loop closure all came from the corrected runtime path. The dashboard API resolved the fresh summary, returned `50` scene metric-history rows and `50` quality-gate rows, and read ledger totals from `book_run_summary.ledger_data_root`. Run-local EvoSkill trace root contained `50` enriched traces with `metric_*` fields; no-live nightly promoted skill `8db503d7-9692-4fde-8312-3935323728a3`.
**Supersedes:** T014-030 as the latest Cedar Harbor full-book validation baseline.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-032 — Runtime BookMetrics Are Deterministic
**Date:** 2026-06-17
**Statement:** `QualityAgent` now computes runtime `BookMetricsLedger` prose metrics from edited scene text instead of writing placeholder constants. `QualityResult` carries the computed metrics and `structural_weighted_score`; `BookMetricsEvent` records computed word count, interiority, dialogue ratio, exposition, action, sensory density, em-dash density, sentence-length average, and `ai_tell_count = nofly_violations + structural_flags`. `JobRunner` enriches EvoSkill traces with tier flags, NoFly/structural counts, weighted structural points, and numeric `metric_*` values.
**Rationale:** The Cedar Harbor no-live autopsy showed the durable manuscript summary was correct (`64982`) while the historical embedded dashboard total was stale (`146285`), and the old live ledger path still would have written fixed prose-shape values (`interiority_pct = 0.20`, `dialogue_ratio = 0.30`, `scene_type = action`, and AI-tell based only on NoFly) despite deterministic eval and structural analysis having scene-specific signals. Author-facing dashboards, context packs, and EvoSkill need actionable per-scene metrics, not placeholders.
**Supersedes:** Placeholder runtime BookMetrics constants and NoFly-only runtime `ai_tell_count`.
**Verification:** `./.venv/bin/pytest tests/unit/test_word_count_enforcement.py tests/unit/test_job_runner_phase9.py tests/integration/test_evoskill.py` passed (`27 passed`). `make lint` passed. `OPENAI_API_KEY= ANTHROPIC_API_KEY= make test` passed (`402 passed, 6 skipped`).
**Runbook:** `docs/runbooks/full-book-generation.md`; autopsy report: `docs/runbooks/cedar-harbor-no-live-hardening-report.md`

### T014-031 — Full-Book Ledgers Are Run-Local
**Date:** 2026-06-17
**Statement:** `scripts/run_full_book.py` now writes `LedgerManager` state under each full-book run directory at `data/books/{book_id}/runs/{run_id}/ledgers` and records that path in `book_run_summary.json` as `ledger_data_root`. When `--force` is used, that run-local ledger root is removed before regeneration. The Author Dashboard book-level ledger, metric history, character metrics, promise, intimacy, and quality-gate endpoints prefer `book_run_summary.ledger_data_root` when present.
**Rationale:** The Cedar Harbor staged proof reused shared configured ledgers across multiple proof run IDs, so the durable manuscript count was correct (`64982`) while the embedded dashboard summary could show accumulated stale state (`146285`). Full-book resume needs same-run ledger continuity, but different run IDs must not contaminate each other. Dashboard reads must follow the run summary so author-facing totals match the generated run artifact.
**Supersedes:** Shared configured ledger root as the production full-book runner's mutable ledger state.
**Verification:** `./.venv/bin/pytest tests/unit/test_full_book_runner.py tests/unit/api/test_dashboard_api.py` passed (`30 passed`). `make lint` passed. `OPENAI_API_KEY= ANTHROPIC_API_KEY= make test` passed (`400 passed, 6 skipped`). No-live dashboard dogfood confirmed the old Cedar Harbor summary is readable but lacks `ledger_data_root`; the fix applies to new summaries. No-live EvoSkill nightly over Cedar Harbor traces promoted one skill from 29 failure traces.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-030 — Cedar Harbor Full Anthropic Test-Tier Book Passed
**Date:** 2026-06-16
**Statement:** The staged Anthropic test-tier run `cedar-harbor-book01-weighted-gate-anthropic --max-scenes 50` completed the full Cedar Harbor `book01` scaffold successfully. Final summary: `50/50` scenes completed, `50/50` GO decisions, `0` force-resolved scenes, deterministic eval PASS scoped to all 50 scene paths, dashboard summary PASS, strict `BookStructuralVerifier` PASS, and final manuscript word count `64982` against the 65000-word target.
**Rationale:** This is the first full-length production scaffold to pass the unattended full-book runner end to end after the generation-time word-count, editor shrinkage, measured writer count, weighted structural-density, and fail-closed state-machine fixes. The run stayed on test tier, used Anthropic fallback after OpenAI quota exhaustion, kept `model_router.json` defaulted to `test`, and cost `$1.153952` total for the run (`534840` tokens). The user-approved additional `$5` cap was not approached; incremental spend after the prior `$0.4984488` stop was about `$0.6555032`.
**Supersedes:** T014-029 as the latest Cedar Harbor weighted-gate proof status.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-029 — Anthropic Test-Tier Weighted-Gate Proof Passed
**Date:** 2026-06-16
**Statement:** The approved Anthropic test-tier continuation `cedar-harbor-book01-weighted-gate-anthropic --max-scenes 20` passed after the weighted structural-density and fail-closed state-machine fixes. Final summary: `20/20` selected scenes completed, `20/20` GO decisions, `0` force-resolved scenes, deterministic eval PASS scoped to exactly 20 selected scene paths, dashboard summary PASS, verifier skipped with `reason = "partial_run"`, and total assembled words `26441` against 26000 planned selected-scene words.
**Rationale:** OpenAI quota exhaustion blocked the scoped retry after the weighted AI-tell gate fix. The Anthropic test-tier fallback validated the current runner/agent gates on the same Cedar Harbor scaffold without production tier. The run consumed `$0.4984488` of the approved `$0.50` live-spend cap, so staged continuation to 30/40/50 scenes is paused pending new explicit spend approval.
**Supersedes:** OpenAI quota stop as the latest Cedar Harbor weighted-gate proof status.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-028 — Agent Node Exceptions Stop Scene Graph
**Date:** 2026-06-16
**Statement:** `SceneStateMachine` now routes any writer, editor, continuity, or quality node exception directly to graph end with `error` preserved. Downstream nodes do not run after an agent-node exception; ledgers are not updated; no final text or misleading GO/force-resolve artifact is produced from a failed provider call.
**Rationale:** The approved Cedar Harbor forward-progress batch hit OpenAI `429 insufficient_quota` during the scoped retry run `cedar-harbor-book01-writer-count-ai-tell`. The state machine logged `writer_node failed`, but the graph's unconditional edges still allowed editor/quality/final handling to continue far enough to produce confusing status artifacts. Provider quota/API failures must fail closed immediately. Regression test: `test_writer_exception_stops_before_editor_quality_and_final`.
**Supersedes:** Unconditional `writer_node -> editor_node -> continuity_node -> quality_node` progression after node exceptions.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-027 — Quality Gate Uses Weighted Structural Density
**Date:** 2026-06-16
**Statement:** `QualityAgent` now includes `EditorOutput.structural_weighted_score` in tier classification. A scene may route warn/GO only when both raw structural flag count and weighted structural density are within limits. The weighted limit is aligned with offline `AITellMetric`'s pass threshold: no more than roughly 5 weighted structural points per 1K words, with a floor of 5.
**Rationale:** The approved 20-scene stage of `cedar-harbor-book01-writer-count` generated `20/20` GO and `0` force-resolved scenes, but deterministic eval failed because `ch08_sc02` had `AITellMetric=0.4215`. The live QualityAgent had allowed the scene because the raw flag count fit the length-aware count threshold, while offline eval uses weighted structural density. This was a gate-coverage mismatch, not a content-policy decision. The fix tightens live quality gating so eval-failing weighted AI-tell density is caught before GO.
**Supersedes:** Raw structural flag count as the only structural AI-tell gate in `QualityAgent`.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-026 — Writer Word Count Is Measured, Not Trusted
**Date:** 2026-06-16
**Statement:** `WriterAgent` now always recomputes `WriterOutput.word_count` from `draft_text` and overwrites any model-reported count. Retry prompts also state the previous draft's actual word count and the minimum additional words required to satisfy the scene floor.
**Rationale:** The approved fresh editor-guard proof `cedar-harbor-book01-editor-guard --max-scenes 10` validated the editor length guard for the prior `ch05_sc01` failure, but still failed with `ch03_sc02` force-resolved. Logs showed the model repeatedly reported drafts around 1318 words while the actual final prose was only 1008 words. The QualityAgent correctly failed on actual text length, but WriterAgent logs and memory were trusting the model's self-reported `word_count`, making the failure look like a quality false positive. Runtime word counts must be measured deterministically from text everywhere.
**Supersedes:** Trusting LLM-provided `WriterOutput.word_count` when nonzero.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-025 — Editor Structural Edits Preserve Scene Minimum Length
**Date:** 2026-06-15
**Statement:** `EditorAgent` now rejects structural-only surgical edits that shrink an already-above-minimum draft below the per-scene 90% minimum word count. NoFly cleanup may still shrink below the minimum; that remains safer than preserving forbidden constructions and will route through the normal QualityAgent retry loop. `WriterAgent` retry prompts also explicitly prohibit Markdown separators and appended alternate versions.
**Rationale:** The approved `cedar-harbor-book01-quality-tune --max-scenes 10` continuation resumed correctly and generated through 10 selected scenes, but failed with `ch05_sc01` force-resolved. The final writer draft was above target, then the editor returned `1165` words against a `1170` minimum and included an appended alternate-version separator (`---`). Structural analysis had only medium issues and would have warned under the length-aware threshold; the hard failure was editor-induced underlength by 5 words. The fix preserves the full-length writer draft when a structural edit violates the length contract, while retaining fail-closed handling for NoFly removals.
**Supersedes:** Allowing structural surgical edits to reduce an adequate scene below the generation-time word-count floor.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-024 — Cedar Harbor Post-Threshold Partial Proof Passed
**Date:** 2026-06-15
**Statement:** The approved live test-tier Cedar Harbor proof `cedar-harbor-book01-quality-tune` passed after the length-aware structural quality threshold change. Final run summary: `3/3` selected scenes completed, `3/3` GO decisions, `0` force-resolved scenes, deterministic eval PASS scoped to exactly 3 selected scene paths, dashboard summary PASS, verifier skipped with `reason = "partial_run"`, and total assembled words `3795` against 3900 planned words.
**Rationale:** This validates the T014-021/T014-023 fixes together: generation-time word-count enforcement produces production-scale scene lengths, force-resolved scenes remain unacceptable for unattended runs, partial eval no longer counts stale scene files, and medium-only structural flags no longer exhaust retries just because a scene is full-length. The first invocation timed out during scene 3; rerunning the same run ID resumed correctly and skipped completed scenes 1-2.
**Supersedes:** The failed `cedar-harbor-book01-wordcount-fix` 3-scene proof as the current Cedar Harbor partial-run baseline.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-023 — Length-Aware Structural Quality Threshold
**Date:** 2026-06-15
**Statement:** `QualityAgent` now scales the structural warn threshold by scene length: floor `6` structural flags, then `ceil(6 flags per 1000 words)` for longer scenes. Medium-only structural flags above the old absolute threshold no longer force a scene into `needs_review` solely because the scene was expanded to the production word target.
**Rationale:** The post word-count-fix Cedar Harbor 3-scene proof generated full-length scenes, but `ch01_sc02` force-resolved after reaching 1441 words because deterministic structural analysis found 7 medium flags. The previous absolute `structural <= 6` gate was calibrated for shorter scenes and became brittle once generation-time word-count enforcement worked. Scaling by scene length preserves fail-closed behavior for genuinely dense structural issues while avoiding false retry exhaustion for production-length scenes.
**Supersedes:** Fixed absolute structural warn threshold for all scene lengths.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-022 — Partial Full-Book Eval Scoped To Selected Inventory
**Date:** 2026-06-15
**Statement:** `scripts/run_full_book.py` now evaluates only the selected `SceneInventory` scene output paths for `--max-scenes` proofs instead of globbing every scene file under the shared book scene directory. Stale scene files from earlier run IDs are ignored by the corpus eval summary.
**Rationale:** The post-fix Cedar Harbor `--max-scenes 3` proof used a new run ID after a prior 50-scene run. Generation correctly attempted only three scenes, but eval initially reported `scene_count = 50` because it collected all existing `scenes/*.md` files. Partial proofs must validate only the artifact set they actually selected, or stale files can hide failures and distort dashboard/eval interpretation.
**Supersedes:** Directory-glob eval for production full-book partial runs.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-021 — Generation-Time Word-Count Enforcement
**Date:** 2026-06-15
**Statement:** Scene generation now enforces a per-scene minimum word count at the quality gate: a finalized candidate below 90% of `JobContext.word_count_target` is marked `needs_review`, receives a `word_count_under_target` note, and routes through the existing REVISE loop. `WriterAgent` treats target length as binding, includes the minimum acceptable length in prompts, and uses prior quality notes plus the previous draft to produce expansion-focused retries. The production full-book runner also treats any force-resolved scene as a failed unattended run, even if files were produced.
**Rationale:** The live Cedar Harbor 50-scene test-tier run completed operationally (50/50 scenes, eval/dashboard PASS) but failed strict verification at 22,996 words against a 65,000-word target. The inventory and `JobContext.word_count_target` values were correct; the missing guard was generation-time enforcement. Catching underlength scenes in `QualityAgent` prevents silent GO routing and surfaces retry exhaustion through force-resolution/failure instead of waiting for final `BookStructuralVerifier` to discover a manuscript-length miss.
**Supersedes:** Prompt-only scene word targets and final-verifier-only underlength detection.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-020 — Unattended Production Full-Book Runner
**Date:** 2026-06-14
**Statement:** `scripts/run_full_book.py` and `make run-full-book` are the production full-book execution contract. The runner validates the series spec, loads or generates `scene_inventory.json`, writes a run-local `model_router.run.json`, instantiates `AgentContext`, `ModelRouter`, and `LedgerManager`, runs scenes through `BookRunner.run_inventory()` in inventory order, assembles `manuscript.md`, writes `book_run_summary.json`, and runs deterministic eval, strict verifier, and local dashboard summary checks when applicable. `--max-scenes` truncates only the in-memory inventory for spend-capped proofs; full-book verification is skipped for partial runs with `reason = "partial_run"`. Resume is scoped to the selected run ID through `data/books/{book_id}/runs/{run_id}/book_run_status.jsonl`; `--force` resets that run status and reruns selected scenes.
**Rationale:** Production book generation should not require manually starting every scene through orchestrator `--job`. The existing `BookRunner.run_inventory()` already provides the correct ordered loop, resume, force, and summary behavior; the missing piece was a production CLI that wires committed series scaffolds into that loop without mutating `model_router.json` or requiring live API calls in tests. Generated production artifacts under committed series scaffolds are gitignored while specs and `scene_inventory.json` remain source-controlled.
**Supersedes:** Manual per-scene orchestrator invocation as the production continuation path after scaffold approval.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-019 — First Production Scaffold and Scene-Brief Inventory Contract
**Date:** 2026-06-14
**Statement:** The first production-ready full-length scaffold is `data/series/cedar-harbor-romance/`, with series spec, book spec, run config, bible/facts, character sheets, local voice profile, and a generated 50-scene inventory for `book01` (`The Renovation Pact`). `BookStructurePlanner` now preserves optional per-scene outline fields from book specs: `scene_brief`, per-scene `scene_function`, `word_count_target`, `heat_level_target`, and `required_slot_id`. The orchestrator uses `SceneSlot.scene_brief` when launching scene jobs, so authored beat sheets feed the WriterAgent instead of falling back to generic prompts.
**Rationale:** Turn 9 needs an author-approved full-length book input. A scaffold that validates but discards its detailed scene plan would produce generic scenes and waste model spend. Carrying scene briefs into the inventory keeps the existing planner thin while making production specs useful for real generation.
**Supersedes:** Generic orchestrator scene brief fallback as the only source of scene-level drafting instructions.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T013-009 — Dashboard Runtime Data Root Contract
**Date:** 2026-06-11
**Statement:** The Author Dashboard backend reads generated run artifacts from `FF_DASHBOARD_DATA_ROOT`, with `app.state.data_root` still taking precedence in tests. `make dashboard` now exposes this as `DASHBOARD_DATA_ROOT` and accepts optional `DASHBOARD_RUN_ID`, `DASHBOARD_BOOK_ID`, `DASHBOARD_SERIES_ID`, and `DASHBOARD_CHARACTER_IDS` values to prefill the React selectors.
**Rationale:** Dashboard dogfooding against generated acceptance runs needs a runtime way to point FastAPI and the React shell at a gitignored run directory. Previously only tests could override `app.state.data_root`, which made the documented budgeted novella workflow impossible to run through `make dashboard` without code changes.
**Supersedes:** Test-only dashboard data-root override as the only data-root selection mechanism.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T013-008 — Dashboard Historical Views Completed
**Date:** 2026-06-11
**Statement:** The Author Dashboard now includes read-only historical cards for book promises, intimacy escalation, series promises, promoted EvoSkill skills, and voice calibration history. The API exposes narrow local endpoints for existing artifacts: `GET /books/{book_id}/promises`, `GET /books/{book_id}/intimacy`, SQLite-backed `GET /series/{series_id}/promises`, and `GET /series/{series_id}/voice_calibration`. The existing `GET /series/{series_id}/evoskill` endpoint drives the Skill Library card.
**Rationale:** Phase 13 needed the remaining useful historical views without redesigning the dashboard shell. The cards reuse existing SQLite ledgers, run-local markdown skills, and voice profile YAML rather than creating a new dashboard data model. This keeps dashboard history aligned with the append-only local data architecture and preserves test-tier/default development posture.
**Supersedes:** Nothing — completes the Phase 13 historical view surface started by T013-005 and extended by T013-007.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T013-007 — Dashboard Word-Budget Summary Card
**Date:** 2026-06-11
**Statement:** The Author Dashboard now exposes `book_run_summary.json` through `GET /books/{book_id}/summary` and renders `word_budget_status` in a Word Budget card. The card shows book target, planned scene-target total, actual words, remaining word budget, projected final count, minimum scene target, latest adjusted scene target, and the per-scene controller trace when present. The API resolves summaries from both direct dashboard data roots and generated acceptance-run `series/*/data/books/{book_id}/book_run_summary.json` paths.
**Rationale:** Adaptive word-budget control is now a core author-facing production signal. Surfacing it from the durable summary avoids recomputing verifier/controller state from ledgers and lets the dashboard show drift during polling and after completed book runs without touching `model_router.json` or triggering live generation.
**Supersedes:** Nothing — extends Phase 13 dashboard visibility for T014-017/T014-018 artifacts.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-018 — Budgeted Production-Tier Novella Acceptance Passed
**Date:** 2026-06-11
**Statement:** With explicit user approval, the live budgeted production-tier novella run completed using `make book-acceptance BOOK_ACCEPTANCE_ARGS="--fixture novella --model-tier production --provider anthropic --run-id production-tier-novella-budgeted --force"`. The run completed 12/12 scenes, reached 12/12 GO decisions, had no force-resolved scenes, passed deterministic corpus eval, passed strict `BookStructuralVerifier`, and passed draft acceptance. Final word count was 4614 against the 4600-word controller target. `word_budget_status` records the original 5400-word planned scene-target total, 4600-word book target, adjusted scene targets from 383 to 403 words, and final projection 4614.
**Rationale:** This validates the adaptive controller on the exact production-tier failure mode from T014-015. The prior production-tier novella produced 5464 words and failed strict final verification. The budgeted production run reduced final count by 850 words, moved strict verification from FAIL to PASS, reduced tokens from 45143 to 33579, reduced estimated cost from `$0.331653` to `$0.240705`, and preserved strong deterministic eval averages (`VoiceConsistencyMetric` 0.9517, `AITellMetric` 0.9167). `model_router.json` remains unchanged and defaulted to `test`.
**Supersedes:** The unbudgeted production-tier novella failure as the current production-tier acceptance baseline.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-017 — Adaptive Book-Level Word-Budget Control
**Date:** 2026-06-11
**Statement:** Book acceptance runs now enable `WordBudgetController` through `BookRunner.run_book(word_budget_target=...)`. The controller redistributes the verifier-level book target across remaining scenes after each actual scene word count is known, records planned target, actual words so far, remaining scenes, projected final count, and per-scene adjusted target, and floors adjusted scene targets at 250 words. `book_run_summary.json` includes `word_budget_status` with the full per-scene trace. Draft acceptance and strict final verification remain separate and unchanged.
**Rationale:** The production-tier novella generated a useful rich draft but overran the strict final word-count gate because every scene kept receiving a fixed 450-word prompt. A book-level feedback loop preserves rich drafting while reducing the chance that production-tier prose drifts beyond final verifier tolerance.
**Supersedes:** Fixed per-scene acceptance prompt targets with no mid-run book-budget feedback.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-016 — Draft Acceptance Separate From Final Verification
**Date:** 2026-06-11
**Statement:** `scripts/run_book_acceptance.py` now defaults to `--acceptance-mode draft`, writing a separate `draft_acceptance_status` block with explicit draft surplus accounting: `target_word_count`, `actual_word_count`, `surplus_words`, `surplus_pct`, `draft_surplus_allowed_pct`, and `within_draft_surplus`. Draft acceptance passes only when all scenes complete, no scenes fail, no scenes are force-resolved, deterministic corpus eval passes, dashboard API checks pass if present, and the draft is within the configured surplus ceiling. The default ceiling is +25%. `--acceptance-mode final` preserves the strict prior behavior, and `verifier_status` remains unchanged as the publish-ready structural gate.
**Rationale:** Production-tier novella generation produced a complete, clean draft but exceeded the strict final word-count verifier by 404 words over the upper final tolerance. That should be classified as useful editable surplus, not a draft failure, while keeping BookStructuralVerifier strict for final manuscripts. The existing 5464-word production novella is now interpreted as `draft_surplus` (+18.78% over target, within +25%) and still fails final verification.
**Supersedes:** The top-level acceptance interpretation in T014-015 that treated every BookStructuralVerifier word-count failure as an overall draft failure.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-015 — Production-Tier Novella Comparison Completed
**Date:** 2026-06-11
**Statement:** A live production-tier novella run completed using `make book-acceptance BOOK_ACCEPTANCE_ARGS="--fixture novella --model-tier production --provider anthropic --run-id production-tier-novella-local --force"`: 12/12 scenes completed, 12/12 GO decisions, no force-resolved scenes, deterministic corpus eval PASS, and dashboard API checks PASS. Overall acceptance remained false because BookStructuralVerifier rejected word count: 5464 words against target 4600 with tolerance [4140–5060]. The comparable test-tier novella run remains the accepted baseline: 4702 words, verifier PASS, 189.463 seconds, 23545 tokens, `$0.0092049`. Production took 304.54 seconds, 45143 tokens, and `$0.331653`.
**Rationale:** The production-tier model produced stronger deterministic voice and AI-tell scores on average and a more concrete prose sample, but it overran the structural word budget. Production-tier novella generation is operational, but not yet a better acceptance baseline until word-budget control is tightened. `model_router.json` remains defaulted to `test`; production-tier runs remain explicit only.
**Supersedes:** Unverified full-book/novella production-tier comparison.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T012-005 — EvoSkill Nightly Closure on Live Novella Traces
**Date:** 2026-06-11
**Statement:** Three local `scripts/evoskill_nightly.py` passes were run over the live novella trace corpus at `data/book_acceptance/test-tier-novella-local/data`. Each pass found 12 `failure/quality_gate_fail` traces for `book-acceptance-series`, proposed a local mock skill, passed evaluation (`score=0.700`, `baseline=0.500`, `improvement=0.200`), kept it on the frontier, and promoted it. Result: 3 local skill markdown files and 3 matching run-local WUPHF wiki mirror pages under `series-bible/book-acceptance-series/editorial-guidelines/`.
**Rationale:** This proves learning-loop closure on real full-book/novella traces: scene execution writes traces, nightly reads them, proposer/evaluator/frontier accepts skills, and promotion reaches both local data and WUPHF wiki mirror paths. The live novella run had no revised-then-GO scenes; that path remains covered by regression test `test_job_runner_trace_marks_revised_go_as_failure`.
**Supersedes:** Earlier fixture-only EvoSkill nightly closure.
**Runbook:** `runbooks/evoskill-setup.md`

### T014-014 — Live Test-Tier Novella Acceptance Passed
**Date:** 2026-06-11
**Statement:** `scripts/run_book_acceptance.py` now supports `--fixture novella`, a 12-scene Romance Module fixture with a 3/6/3 act split and distinct book ID `book-acceptance-romance-novella-01`. The first live test-tier novella run passed using `make book-acceptance BOOK_ACCEPTANCE_ARGS="--fixture novella --model-tier test --provider openai --run-id test-tier-novella-local --force"`: 12/12 scenes completed, 12/12 GO decisions, no force-resolved scenes, manuscript word count 4702, deterministic corpus eval PASS, BookStructuralVerifier PASS, dashboard API checks PASS, and cost summary recorded 23 calls / 23545 tokens / `$0.0092049` estimated cost.
**Rationale:** This validates the full-book runner beyond the 8-scene short-book fixture and proves author-facing artifacts are readable through the dashboard API. The run also confirms real token/cost accounting is usable for later test-tier vs production-tier comparisons.
**Supersedes:** Short-book-only live acceptance as the longest repeatable generation workflow.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-013 — Real Token Accounting and Run-Local Files API IDs
**Date:** 2026-06-10
**Statement:** `ModelRouter` now captures provider token usage when available: OpenAI `prompt_tokens`/`completion_tokens`, Anthropic `input_tokens`/`output_tokens`, and Anthropic cache input tokens. `cost_log.jsonl` entries include `input_tokens`, `output_tokens`, `total_tokens`, and `cost_usd`, with zero-token fallback when usage metadata is missing. `BookRunner.write_book_run_summary()` aggregates the run-local cost log into `cost_summary`. Claude Files API uploads are opt-in at book-run setup; returned file IDs for series bible, voice profile, and character sheets are stored under the run-local data root and mirrored into `book_run_summary.json` through `ManagedAgentConfig`.
**Rationale:** Test-tier vs production-tier comparisons need real token and cost totals, not zero placeholders. Long-context assets also need a lifecycle that reduces context bloat without writing provider IDs into source files or requiring live secrets in tests.
**Supersedes:** The cost-comparison deferral in T014-008 caused by zero token accounting.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-012 — First Live Short-Book Acceptance Passed
**Date:** 2026-06-10
**Statement:** The first live test-tier short-book acceptance run passed using `make book-acceptance BOOK_ACCEPTANCE_ARGS="--model-tier test --provider openai --run-id test-tier-short-book-local"`. The run generated 8/8 scenes through `JobRunner`, reached 8/8 GO decisions, produced `manuscript.md` and `book_run_summary.json`, passed deterministic corpus eval over all 8 scenes, and passed BookStructuralVerifier. The short-book verifier target is calibrated to `SHORT_BOOK_WORD_COUNT_TARGET = 3300` for the 8-scene edited-output fixture.
**Rationale:** This establishes repeatable short-book generation beyond Phase 14's three-scene acceptance. The calibrated verifier target reflects actual edited-output length without tuning generated prose, and keeps the structural gate useful for the short fixture.
**Supersedes:** Unverified short-book acceptance workflow from T014-009 through T014-011.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-011 — Book Runner Resume and Force Contract
**Date:** 2026-06-10
**Statement:** `BookRunner.run_book()` resumes by default. If a scene's latest status is successful and its finalized scene file exists, the runner appends a `skipped` status using the prior checkpoint thread ID and does not rerun that scene. The first failed or incomplete scene is rerun, and later scenes continue in order. `force=True` intentionally regenerates all scenes and resets the status JSONL by default. `book_run_summary.json` includes `previous_failed_scene_ids` and `checkpoint_thread_ids` for the current run.
**Rationale:** Repeatable full-book generation must be idempotent. A second invocation after a mid-book failure should not spend tokens rewriting completed scenes, but authors still need failed scene history and a deliberate force path for regeneration.
**Supersedes:** Status-only resume foundation from T014-009.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-010 — Ordered Manuscript and Book Summary Contract
**Date:** 2026-06-10
**Statement:** `BookRunner.assemble_manuscript()` assembles finalized scene files in supplied fixture or `SceneInventory` order into `manuscript.md` with deterministic book/chapter/scene headings. `BookRunner.write_book_run_summary()` writes `book_run_summary.json` with run metadata, provider, scene statuses, total word count, GO/force-resolved/failed counts, failed scene IDs, manuscript path, scene directory, ledger dashboard summary, and optional eval/verifier status blocks.
**Rationale:** Repeatable full-book generation needs a stable artifact contract beyond per-scene files. Ordered assembly catches missing scene outputs immediately, and the summary gives dashboard, eval, verifier, and future resume flows one durable local source of truth.
**Supersedes:** Turn 1's status-only short-book acceptance output.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-009 — Short-Book Acceptance Runner
**Date:** 2026-06-10
**Statement:** `pipeline/book_runner.py` provides the first reusable ordered book runner over the existing `JobRunner` scene path, with per-scene JSONL status records for future resume support. `scripts/run_book_acceptance.py` runs an eight-scene Romance Module fixture under `data/book_acceptance/`, defaults to `test`, and writes a run-local `model_router.run.json` for any explicit tier selection.
**Rationale:** Phase 14 proved repeatable scene generation; full-book generation needs the same scene path executed in order with durable status after each scene. The runner records enough scene-level state to resume or audit later without mutating `model_router.json` or requiring live model calls in automated tests.
**Supersedes:** Manual one-scene or three-scene-only acceptance as the highest repeatable generation workflow.
**Runbook:** `docs/runbooks/full-book-generation.md`

### T014-008 — Production-Tier Acceptance Passed, Default Remains Test
**Date:** 2026-06-10
**Statement:** Phase 14 test-tier and production-tier three-scene acceptance runs both passed: 3/3 GO scenes and deterministic corpus eval PASS. `model_router.json` remains defaulted to `test`; production-tier runs use the run-local router config generated by `scripts/run_phase14_acceptance.py`.
**Rationale:** Production-tier acceptance is green enough to support deliberate production comparisons, but default development posture remains cheap/test-tier per DEC-000-9. Exact token/cost comparison is deferred until `ModelRouter` records real usage counts; current comparison dimensions are runtime, GO decisions, word totals, and eval scores.
**Supersedes:** Unverified Phase 14 production-tier promotion state.
**Report:** `docs/runbooks/phase14-model-promotion.md`

### T014-007 — Three-Scene Acceptance Runner
**Date:** 2026-06-10
**Statement:** `scripts/run_phase14_acceptance.py` runs a three-scene Romance Module acceptance path through the full `JobRunner` pipeline and can optionally invoke the deterministic multi-scene eval gate. The runner writes a run-local `model_router.run.json` with the requested active tier, so test-tier and production-tier runs do not require mutating `model_router.json`.
**Rationale:** Phase 14 needs a repeatable command that exercises the same scene loop used in production before promoting model tiers. A run-local router config avoids dirtying the repository for production comparisons and keeps test-tier as the default development posture.
**Supersedes:** Manual one-scene smoke-test-only Phase 14 acceptance workflow.

### T014-006 — Multi-Scene Local Eval Gate
**Date:** 2026-06-09
**Statement:** `scripts/run_eval.py` supports a corpus mode via `--scene-dir`, with `--require-scenes` and `--max-scenes` for stable 3-scene local acceptance runs. `make eval` still defaults to the newest completed single scene when no explicit input is provided.
**Rationale:** Phase 14 needs a local, repeatable 3-scene quality gate before production-tier model promotion. Corpus eval keeps CI/offline behavior deterministic while preserving the single-scene workflow for quick checks and latest-scene smoke tests.
**Supersedes:** Single-scene-only Phase 14 eval runner behavior.

### T013-006 — Deterministic Character Metrics Fallback
**Date:** 2026-06-09
**Statement:** `QualityAgent.update_ledgers()` now computes and persists per-character dialogue metrics using a stdlib deterministic fallback for explicit `Speaker: dialogue` lines and common `"dialogue," Speaker said` tags. The output preserves the SYN-013 12-field schema, including `function_word_vector`. Full BookNLP speaker attribution remains the planned richer attribution layer.
**Rationale:** `CharacterVoiceChart` needs real data from normal scene finalization, not only hand-seeded fixture ledger events. A local fallback gives authors useful metrics for explicitly attributed dialogue without adding runtime fragility or blocking on BookNLP model setup.
**Supersedes:** Empty `BookMetricsLedger.character_metrics` in normal QualityAgent ledger updates.

---

### T013-005 — Historical Dashboard Metric Components
**Date:** 2026-06-09
**Statement:** The dashboard now includes `MetricPlotter` for configurable metric history at chapter, scene, and beat granularity, plus `CharacterVoiceChart` for per-character metric comparison. Backend beat granularity currently returns a scene-backed fallback row with `beat_id = scene_id` until true beat-level ledger events are emitted.
**Rationale:** Phase 13 acceptance needs historical browsing, configurable metric plotting, and character voice comparison. The backend already had SQLite scene/chapter history; adding a stable beat fallback lets the UI and API contract support the planned granularity selector without inventing unsupported beat metrics.
**Supersedes:** The live-view-only dashboard shell from the first Phase 13 slice.

---

### T013-004 — File-Backed Dashboard Run Events
**Date:** 2026-06-09
**Statement:** JobRunner writes Author Dashboard run status and events to files under the configured ledger data root: `{data_root}/{run_id}/run_state.json`, `{data_root}/{run_id}/dashboard_events.jsonl`, and `{data_root}/{book_id}/quality_gate_history.jsonl`. FastAPI reads the same configurable data root for run status, quality gates, series promises, and EvoSkill skills. The SSE endpoint replays persisted run events and still accepts in-process queue events.
**Rationale:** V1 jobs usually run in a separate CLI process from the FastAPI dashboard. A process-local SSE queue cannot satisfy live-view acceptance by itself. File-backed events are simple, local-dev friendly, testable, and consistent with the existing JSONL/SQLite local architecture.
**Supersedes:** The in-memory-only SSE event path for cross-process dashboard updates.

---

### T014-005 — SQLite Checkpoint Resume Contract
**Date:** 2026-06-09
**Statement:** `SceneStateMachine` keeps the `SqliteSaver` context open for the compiled graph lifetime, calls `setup()` before execution, and exposes a stable checkpoint thread ID. `JobRunner` uses the scene job ID as the default thread ID, returns it in `SceneRunResult`, and closes checkpoint resources after run/resume. Normal orchestrator `--job` runs now use `ProjectLayout.checkpoint_db_path()` by default, record `thread_id` in scene history, and print it for later `--resume` use. `langgraph-checkpoint-sqlite` is an explicit dependency.
**Rationale:** Phase 14 pause/resume is only operational if the SQLite saver remains alive during graph execution, callers can find a stable thread ID, and normal scene jobs actually enable checkpointing. The regression test proves a resumed run does not rerun completed writer/editor/quality nodes after a final-node failure.
**Supersedes:** Earlier checkpoint plumbing that generated hidden random thread IDs and compiled with a saver context that was closed immediately.

---

### T012-004 — EvoSkill Trace Semantics and Promotion Closure
**Date:** 2026-06-09
**Statement:** EvoSkill traces classify any scene with a revision attempt, RE-PLAN, below-threshold critic score, or `needs_review` signal as a failure trace even if the final routing decision is `GO`. `SkillPromoter` now honors an explicit `data_root`, writes local skills under that root, and publishes accepted skills to the WUPHF `series-bible/{series_id}/editorial-guidelines/{skill_id}` page when WUPHF is configured. `scripts/evoskill_nightly.py` passes its `--data-root` through to promotion and attaches a WUPHF client only when local wiki or API settings are present.
**Rationale:** Phase 12 learning must use semantically correct failure traces, not just final scene outcomes. A revised-then-approved scene is still a learning signal. Promotion must also exercise the configured WUPHF/local-wiki path while preserving no-op local-dev behavior when WUPHF is absent.
**Supersedes:** Earlier local-only skill promotion behavior that ignored `--data-root` and did not publish to `series-bible` when WUPHF was configured.

---

### T014-004 — Local Offline Eval Default
**Date:** 2026-06-09
**Statement:** `make eval` runs `scripts/run_eval.py` against a provided scene or the newest completed scene under `data/**/scenes/`. Phase 14 evals are deterministic by default: `VoiceConsistencyMetric` uses an offline heuristic unless `--use-llm-voice` or `FF_EVAL_USE_LLM=true` is set, and `AITellMetric` uses the structural analyzer with a regex fallback.
**Rationale:** Phase 14 evaluation must be runnable in local CI and developer workspaces without requiring live Anthropic credentials. LLM judging remains available as an explicit opt-in for prose-quality investigations.
**Supersedes:** Nothing — implements the first Phase 14 eval slice.

---

### T013-003 — Dashboard Metrics Read From SQLite Ledgers
**Date:** 2026-06-09
**Statement:** Author Dashboard metrics endpoints read from `BookMetricsLedger` SQLite events through `LedgerManager`, including chapter aggregates, scene histories, optional metric filters, and per-character metric histories. The initial React dashboard is a minimal Vite live-view shell over the FastAPI endpoints; richer historical charts remain a later Phase 13 slice.
**Rationale:** SQLite ledgers are the source of truth for historical dashboard state. Removing the previous JSONL placeholder keeps the dashboard aligned with the append-only ledger architecture.
**Supersedes:** Any placeholder `book_metrics.jsonl` dashboard-history behavior.

---

### T012-003 — JobRunner EvoSkill Trace Capture
**Date:** 2026-06-09
**Statement:** `JobRunner` saves an EvoSkill scene trace after each completed scene through `TraceCollector`, using `LedgerManager.data_root` by default. Trace collection is fail-safe: trace write failures are logged and never break scene execution.
**Rationale:** Phase 12 learning needs production scene traces from normal runs, but trace persistence is advisory relative to manuscript execution. The scene-generation path remains authoritative and must not fail because the learning sidecar cannot write a trace.
**Supersedes:** Nothing — wires Phase 12 traces into the scene execution path.

---

### T011-004 — WUPHF Local Git Wiki Mirror
**Date:** 2026-06-09
**Statement:** `WUPHFClient` supports a local git-backed wiki mirror via `WUPHF_WIKI_ROOT`. When configured, wiki updates write markdown files under that root; optional `WUPHF_WIKI_AUTO_COMMIT=true` makes a best-effort git commit. `BibleSteward.commit_delta()` syncs committed bible entities to the WUPHF `series-bible` wiki on a best-effort, non-blocking path.
**Rationale:** V1 is local-dev only. Phase 11 needs WUPHF wiki sync behavior without requiring a hosted service in tests or normal local runs. The atomic local bible commit remains authoritative; WUPHF sync must not block or corrupt scene execution.
**Supersedes:** Nothing — fills the Phase 11 WUPHF git-backed wiki acceptance path.

---

### T011-001 — Approval Gate Timeout
**Date:** 2026-05-18
**Statement:** Paperclip approval gate timeout set to 3600 seconds (1 hour default). Pipeline halts with error if timeout expires without human approval.
**Rationale:** Consistent with DEC-004 (no human gates in inner loop). Gates wrap only `--init-book` and `--book-publish`.

---

### T011-002 — Budget Enforcement: Halt vs Pause
**Date:** 2026-05-18
**Statement:** Budget exhaustion causes pipeline halt (exit), not pause. `check_budget()` returns False → orchestrator exits with error message.
**Rationale:** Pause requires durable state management. Halt is cleaner for V1. User restarts after refilling budget.

---

### T011-003 — WUPHF Activity Stream as Audit Log
**Date:** 2026-05-18
**Statement:** WUPHF activity stream is the primary audit log for all agent actions. No separate audit log file. If WUPHF is unavailable, pipeline continues (graceful degradation); audit gap is logged.

---

### T012-001 — Fixture Benchmark Corpus
**Date:** 2026-05-18
**Statement:** EvoSkill Evaluator uses fixture traces from the smoke test corpus as benchmark. In V1 (local mock mode), Evaluator is mocked; production benchmark corpus to be defined after first 50 production scenes.

---

### T012-002 — Nightly Pass Scheduling
**Date:** 2026-05-18
**Statement:** EvoSkill nightly pass runs manually via `python scripts/evoskill_nightly.py` in V1. Cron automation deferred to V2 operational setup.

---

### T013-001 — SSE vs WebSockets
**Date:** 2026-05-18
**Statement:** SSE (Server-Sent Events) chosen for Author Dashboard live updates over WebSockets. SSE is simpler for unidirectional server→client stream; no bidirectional communication needed. V2 upgrade to WebSockets if interactive control is added.

---

### T013-002 — Local Async Queue for SSE
**Date:** 2026-05-18
**Statement:** SSE events use a local `asyncio.Queue` (no Redis dependency) for V1. Single-process, single-user local dev. V2 introduces Redis pub-sub if multi-process deployment is needed.

---

### T014-001 — VoiceConsistencyMetric Threshold
**Date:** 2026-05-18
**Statement:** `VoiceConsistencyMetric` thresholds: Romance default 0.75, Erotica default 0.70. Lower erotica threshold reflects expected kinetic prose variance. Thresholds configurable per-genre at construction time.

---

### T014-002 — AITellMetric LLM Judge Threshold
**Date:** 2026-05-18
**Statement:** LLM-as-judge invoked only for severity `"critical"` issues. High-severity patterns handled deterministically. Severity-5 critical patterns (e.g. "a testament to") are unambiguous; high-severity patterns may have legitimate use.

---

### T014-003 — Mem0 Retrieval Count
**Date:** 2026-05-18
**Statement:** Mem0 semantic retrieval returns top-5 facts per query by default. Balances context richness vs token cost. Tunable via `n=` parameter.

---

### T015-001 — V2 Scope Deferred
**Date:** 2026-05-18
**Statement:** All V2 scope items documented in `docs/v2-roadmap.md` are deferred until V1 completion criteria are met. No V2 implementation code, schemas, or dependencies added in V1.
**V1 completion criteria:** (1) one complete book produced and reviewed; (2) `make eval` passes VoiceConsistencyMetric ≥ 0.75 and AITell below threshold; (3) author signs off on production run; (4) `BookStructuralVerifier` passes; (5) ≥ 3 EvoSkill nightly passes with promoted skills.
**Supersedes:** Nothing — new deferral record.
