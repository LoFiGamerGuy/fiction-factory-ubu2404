# Task 015 — V2 Roadmap (Deferred Scope)

```
status: pending
started:
completed:
phase: 15
estimated_hours: 0 (documentation only — no implementation)
depends_on: task-014
```

## Goal

Document V2 scope items as deferred future work with sufficient design detail to resume from. No implementation in this task. V2 begins only after V1 is producing publishable books and the author has completed at least one full series run.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 15 (V2 Roadmap — Deferred)

## Dependencies

- task-014 (production hardening complete; V1 is running)

## Acceptance criteria

- [ ] `docs/v2-roadmap.md` authored with all V2 scope items documented below
- [ ] Each V2 item has: description, prerequisite V1 milestone, design sketch, key open questions, estimated complexity
- [ ] No V2 implementation code anywhere in the codebase
- [ ] No V2 dependencies added to `pyproject.toml`
- [ ] `DECISIONS.md` entry confirming V2 scope is deferred and documenting the V1 completion criteria that gate V2 start

## V2 scope items (document only — do not implement)

### V2.1 — Ensemble Drafting (Drafter A/B/C/D)

**Description.** Multi-model drafting: three or more Drafter variants produce independent drafts; a Selector agent chooses the best or synthesizes. Enables stylistic diversity and quality comparison within a single scene.

**Prerequisites.** V1 producing publishable books. Calibration corpus of ≥ 50 scenes (for Evaluator scoring). Infrastructure: vLLM for hosting Drafter D locally.

**Design sketch.** 
- Drafters A, B, C: existing WriterAgent configured with different model + voice_axes variants.
- Drafter D: fine-tuned local model (see V2.2).
- Selector: QualityAgent variant that scores all drafts and picks the best, or takes a synthesis pass.
- LangGraph: parallel fan-out to all Drafters, fan-in at Selector.

**Key open questions.** How many drafters are cost-effective? What scoring rubric does Selector use? Does ensemble improve measurable voice consistency or just diversity?

**Source.** Bunko §4.

---

### V2.2 — Drafter D Fine-Tuning

**Description.** Fine-tune a local LLM (Unsloth Phase 1 SFT → Axolotl Phase 2 DPO) on the calibration corpus produced by V1 runs. Drafter D becomes a series-specific fine-tuned model.

**Prerequisites.** ≥ 200 finalized scenes with quality scores from V1 production. GPU hardware (AWS GPU or similar). Calibration corpus format exported from BookMetricsLedger + scene text.

**Design sketch.**
- Phase 1 SFT (Unsloth): fine-tune on finalized scenes scored above quality threshold.
- Phase 2 DPO (Axolotl): preference pairs from (FINAL scene, REVISE-rejected draft) pairs logged by ConvergenceController.
- Model served via Ollama locally or vLLM.
- ModelRouter: add `fine_tuned_local` model tier; Drafter D routes there.

**Key open questions.** Which base model? Required GPU VRAM? How often to re-fine-tune as corpus grows? Does per-series fine-tuning outperform prompt-engineering with voice profile?

**Source.** Bunko §6.

---

### V2.3 — Reception Tier

**Description.** Reader feedback loop: Scraper → Reception Analyst → Reader Cohort Modeler. Closes the loop between published books and pipeline configuration.

**Prerequisites.** At least one published book available for review collection. Publication platform with accessible review API or public reviews.

**Design sketch.**
- Scraper (Apify or Bright Data): collect reviews from Amazon, Goodreads, etc. after publication.
- Reception Analyst: categorize reviews (sentiment, specific complaint types, praise patterns).
- Reader Cohort Modeler: update audience_profile.yaml with observed reader responses.
- Feedback loop: updated audience profile flows into next book's ProjectSpec.

**Key open questions.** Privacy compliance for scraped reviews? How to attribute review signals to specific scene-level decisions? Review lag time (months between publish and sufficient review volume)?

**Source.** Bunko §11.

---

### V2.4 — Voice Discriminator (Local Classifier)

**Description.** Local Qwen 2.5 7B classifier fine-tuned to distinguish "this author's voice" from "generic LLM voice." Used as an additional quality gate alongside VoiceConsistencyMetric.

**Prerequisites.** ≥ 100 finalized scenes with known voice compliance status (from VoiceConsistencyMetric scores). GPU hardware for fine-tuning.

**Design sketch.**
- Training: positive examples = scenes with VoiceConsistencyMetric ≥ 0.85; negative = scenes with score < 0.70.
- Fine-tune Qwen 2.5 7B on binary classification task.
- Serve locally via Ollama or vLLM.
- Add `VoiceDiscriminatorMetric` to DeepEval suite.

**Key open questions.** Does a 7B classifier outperform Claude-as-judge for voice scoring? How much fine-tuning data is needed for reliable discrimination? Does it generalize across genres?

**Source.** Bunko §5.3.

---

### V2.5 — harbor eval Ratcheting Suite

**Description.** Replace DeepEval with harbor's ratcheting probe suite for scalable evaluation at production volume.

**Prerequisites.** V1 running with ≥ 500 evaluated scenes. harbor framework evaluated against DeepEval for fiction-domain metrics.

**Design sketch.**
- Define probe suite: VoiceConsistency, AITell, HeatCurveCompliance, PromiseResolution probes.
- Ratcheting: each new run must meet or exceed last run's scores (no regression).
- CI integration: harbor run → ratchet check → pass/fail.

**Key open questions.** harbor public release status? Does ratcheting make sense for creative work (where variance is expected)?

**Source.** Bunko §5.6.

---

### V2.6 — Signing + Watermarking

**Description.** Cryptographic signing (Sigstore), LLM output watermarking (MarkLLM), and OML fingerprinting for provenance and intellectual property protection on published output.

**Prerequisites.** At least one book at publication stage. Legal and compliance review of watermarking requirements.

**Design sketch.**
- Sigstore: sign the output bundle at `--book-publish`; public certificate available for verification.
- MarkLLM: inject statistical watermark into LLM generations at WriterAgent level.
- OML fingerprinting: embed ownership fingerprint in published text.
- Verification: `orchestrator --verify-provenance <book_file>` checks signatures.

**Key open questions.** Does MarkLLM watermarking degrade prose quality? Legal status of LLM watermarking in target jurisdictions? Can watermarks survive editing by a human author?

**Source.** Bunko §7–8.

---

### V2.7 — Temporal Durable Execution

**Description.** Replace LangGraph checkpoint persistence with Temporal for very long runs (20+ books in a series).

**Prerequisites.** LangGraph checkpoint persistence proven insufficient for long runs (observable in V1 production). Temporal infrastructure available locally or on-prem.

**Design sketch.**
- Wrap each LangGraph run in a Temporal workflow.
- Temporal handles retry, durability, and long-running orchestration across process restarts.
- LangGraph continues to manage per-scene state graph; Temporal manages cross-scene and cross-book orchestration.

**Key open questions.** Is Temporal overkill for single-author V1 usage? Does V1 checkpoint persistence prove sufficient for 20-book series?

**Source.** IMPLEMENTATION_PLAN.md Phase 15.

---

### V2.8 — Additional Genre Modules

**Description.** Literary fiction, science fiction, fantasy, mystery genre profiles — each requiring a working author for validation.

**Prerequisites.** Romance Module v1.0 production-validated. At least one published book per target genre (for author validation). Per-genre SME review (equivalent of MBSE Craft Reviews for Romance).

**Design sketch.**
- Each genre module follows the same `genre_profile.schema.json` structure as romance_module_v1.yaml.
- Required elements: scene_function_vocabulary, required_scene_slots, heat_scale (if applicable), structural_conventions, trope_library.
- Literary fiction: no heat_scale; emphasis on thematic resonance, interpretive depth.
- Science fiction: world-building ledger extension; technology-consistency checker in BibleSteward.
- Fantasy: magic-system consistency checker; world-building-heavy BibleSteward rules.
- Mystery: evidence ledger; fair-play constraint (all clues introduced before solution).

**Key open questions.** Who validates each genre module? (Literary/thriller SMEs were identified in MBSE reviews.) How does the trope_library differ across these genres?

**Source.** IMPLEMENTATION_PLAN.md Phase 15 + MBSE Craft Reviews.

---

### V2.9 — EvoSkill → Claude Dreaming Handoff

**Description.** If Claude Managed Agents "Dreaming" feature reaches GA and demonstrably outperforms EvoSkill for fiction-domain traces, wire it as the primary skill evolution mechanism.

**Prerequisites.** Dreaming feature available in production Anthropic API. Comparative evaluation on ≥ 100 fiction failure traces.

**Design sketch.**
- `evoskill_client.py` already has `USE_DREAMING = False` feature flag and `_dreaming_propose_skill()` stub (from Phase 12).
- Implement `_dreaming_propose_skill()` using Managed Agents Dreaming API.
- Evaluate on held-out fiction trace corpus: Dreaming skill quality vs EvoSkill skill quality.
- If Dreaming wins on ≥ 3 of 5 evaluation metrics: flip `USE_DREAMING = True`; deprecate EvoSkill nightly pass.

**Key open questions.** Dreaming API shape (not yet GA as of 2026-05-15). Evaluation metrics for "skill quality" in fiction domain.

**Source.** Bunko §5.5; IMPLEMENTATION_PLAN.md Phase 12 T12.6.

---

## V1 completion criteria gating V2 start

V2 work begins only after ALL of the following:

1. At least one complete book (romance track) produced by V1 pipeline and reviewed by the author.
2. `make eval` passes with VoiceConsistencyMetric ≥ 0.75 and AITellMetric below threshold on that book.
3. Author has reviewed the production run DECISIONS.md log and approved the pipeline's decisions.
4. BookStructuralVerifier passes on the completed book.
5. At least 3 productive EvoSkill nightly passes have run and produced promoted skills.

## Subtasks

- T15.1 — Author `docs/v2-roadmap.md` with all V2 scope items above (copy from this task file; expand design sketches with any additional detail gathered during V1 implementation).
- T15.2 — Add DECISIONS.md entry: "V2 scope deferred. V1 completion criteria: [list above]. No V2 implementation before criteria are met."
- T15.3 — Verify `pyproject.toml` has no V2-only dependencies (vLLM, Unsloth, Axolotl, harbor, Sigstore, MarkLLM, Temporal). If any snuck in, remove them with a decision log entry.
- T15.4 — Commit: `docs(v2): V2 roadmap — all deferred scope items documented (task-015)`.

## Key decisions that affect this task

- **V2 is deferred until V1 produces publishable books (IMPLEMENTATION_PLAN.md Phase 15):** No exceptions. Do not implement any V2 feature speculatively during V1 build.
- **No V2 dependencies in pyproject.toml:** vLLM, Unsloth, Axolotl, harbor, and Temporal are not installed in V1. They are V2 tooling decisions to be made when V2 starts.
- **Feature flags for future switchovers:** The `USE_DREAMING` flag in `evoskill_client.py` (Phase 12) is the only V1 accommodation for a V2 feature. No other V2 accommodations are needed.

## Notes

- This is documentation-only. The only deliverables are `docs/v2-roadmap.md` and a DECISIONS.md entry.
- The design sketches in this task are starting points, not commitments. V2 designs will be refined based on V1 production experience.
- The V1 completion criteria are intentionally concrete: a published book + passing eval metrics + author sign-off. Do not start V2 planning until those criteria are met.

## Out of scope

- Any implementation
- V2 dependency installation
- V2 schemas, code, or tests of any kind
