# V2 Roadmap — Deferred Scope

All items in this document are **deferred** until V1 completion criteria are met.

**V1 completion criteria (all required before V2 begins):**

1. At least one complete book (romance track) produced by V1 pipeline and reviewed by the author.
2. `make eval` passes with `VoiceConsistencyMetric` ≥ 0.75 and `AITellMetric` below threshold on that book.
3. Author has reviewed the production run `DECISIONS.md` log and approved the pipeline's decisions.
4. `BookStructuralVerifier` passes on the completed book.
5. At least 3 productive EvoSkill nightly passes have run and produced promoted skills.

Do not implement any V2 feature before these criteria are met. See `DECISIONS.md` entry `T015-001`.

---

## V2.1 — Ensemble Drafting (Drafter A/B/C/D)

**Description.** Multi-model drafting: three or more Drafter variants produce independent drafts; a Selector agent picks the best or synthesizes across them. Enables stylistic diversity and quality comparison within a single scene.

**Prerequisites.**
- V1 producing publishable books.
- Calibration corpus of ≥ 50 scenes (for Evaluator scoring).
- Infrastructure: vLLM for hosting Drafter D locally.

**Design sketch.**
- Drafters A, B, C: existing `WriterAgent` configured with different model + `voice_axes` variants.
- Drafter D: fine-tuned local model (see V2.2).
- Selector: `QualityAgent` variant that scores all drafts and picks the best, or takes a synthesis pass.
- LangGraph: parallel fan-out to all Drafters, fan-in at Selector.

**Key open questions.**
- How many drafters are cost-effective at production scale?
- What scoring rubric does Selector use — VoiceConsistencyMetric, AITellMetric, or a combined score?
- Does ensemble improve measurable voice consistency, or primarily diversity?

**Estimated complexity.** L — requires LangGraph parallel subgraph + Selector agent design + vLLM infrastructure.

*Source: Bunko §4.*

---

## V2.2 — Drafter D Fine-Tuning

**Description.** Fine-tune a local LLM (Unsloth Phase 1 SFT → Axolotl Phase 2 DPO) on the calibration corpus produced by V1 runs. Drafter D becomes a series-specific fine-tuned model.

**Prerequisites.**
- ≥ 200 finalized scenes with quality scores from V1 production.
- GPU hardware (AWS GPU or similar — deferred per local-dev constraint).
- Calibration corpus format exported from `BookMetricsLedger` + scene text.

**Design sketch.**
- Phase 1 SFT (Unsloth): fine-tune on finalized scenes scored above quality threshold.
- Phase 2 DPO (Axolotl): preference pairs from (FINAL scene, REVISE-rejected draft) pairs logged by `ConvergenceController`.
- Model served via Ollama locally or vLLM.
- `ModelRouter`: add `fine_tuned_local` model tier; Drafter D routes there.

**Key open questions.**
- Which base model? (Qwen 2.5 7B / Llama 3 8B are likely candidates.)
- Required GPU VRAM for fine-tuning and inference?
- How often to re-fine-tune as corpus grows?
- Does per-series fine-tuning outperform prompt-engineering with voice profile?

**Estimated complexity.** XL — requires GPU infrastructure, fine-tuning pipeline, model serving.

*Source: Bunko §6.*

---

## V2.3 — Reception Tier

**Description.** Reader feedback loop: Scraper → Reception Analyst → Reader Cohort Modeler. Closes the loop between published books and pipeline configuration.

**Prerequisites.**
- At least one published book available for review collection.
- Publication platform with accessible review API or public reviews.

**Design sketch.**
- Scraper (Apify or Bright Data — deferred paid services): collect reviews from Amazon, Goodreads, etc. after publication.
- Reception Analyst: categorize reviews (sentiment, specific complaint types, praise patterns).
- Reader Cohort Modeler: update `audience_profile.yaml` with observed reader responses.
- Feedback loop: updated audience profile flows into next book's `ProjectSpec`.

**Key open questions.**
- Privacy compliance for scraped reviews in target jurisdictions?
- How to attribute review signals to specific scene-level decisions?
- Review lag time: months between publish and sufficient review volume.

**Estimated complexity.** XL — requires published books, paid scraping services, audience modeling agent.

*Source: Bunko §11.*

---

## V2.4 — Voice Discriminator (Local Classifier)

**Description.** Local Qwen 2.5 7B classifier fine-tuned to distinguish "this author's voice" from "generic LLM voice." Used as an additional quality gate alongside `VoiceConsistencyMetric`.

**Prerequisites.**
- ≥ 100 finalized scenes with known voice compliance status (from `VoiceConsistencyMetric` scores).
- GPU hardware for fine-tuning.

**Design sketch.**
- Training: positive examples = scenes with `VoiceConsistencyMetric` ≥ 0.85; negative = scenes with score < 0.70.
- Fine-tune Qwen 2.5 7B on binary classification task.
- Serve locally via Ollama or vLLM.
- Add `VoiceDiscriminatorMetric` to DeepEval suite alongside existing metrics.

**Key open questions.**
- Does a 7B classifier outperform Claude-as-judge for voice scoring at lower cost?
- How much fine-tuning data is needed for reliable discrimination?
- Does it generalize across genres (romance vs erotica vs thriller)?

**Estimated complexity.** L — requires fine-tuning data from V1, GPU hardware, DeepEval metric integration.

*Source: Bunko §5.3.*

---

## V2.5 — harbor eval Ratcheting Suite

**Description.** Replace DeepEval with harbor's ratcheting probe suite for scalable evaluation at production volume.

**Prerequisites.**
- V1 running with ≥ 500 evaluated scenes.
- harbor framework evaluated against DeepEval for fiction-domain metrics.
- harbor public release status confirmed.

**Design sketch.**
- Define probe suite: `VoiceConsistency`, `AITell`, `HeatCurveCompliance`, `PromiseResolution` probes.
- Ratcheting: each new run must meet or exceed last run's scores (no regression).
- CI integration: `harbor run` → ratchet check → pass/fail in `make eval`.

**Key open questions.**
- harbor public release status (not confirmed GA as of 2026-05-18)?
- Does ratcheting make sense for creative work where variance is intentional?
- Migration path: how to port existing `VoiceConsistencyMetric` / `AITellMetric` to harbor probes?

**Estimated complexity.** M — primarily tooling swap if harbor API is stable.

*Source: Bunko §5.6.*

---

## V2.6 — Signing + Watermarking

**Description.** Cryptographic signing (Sigstore), LLM output watermarking (MarkLLM), and OML fingerprinting for provenance and intellectual property protection on published output.

**Prerequisites.**
- At least one book at publication stage.
- Legal and compliance review of watermarking requirements in target jurisdictions.

**Design sketch.**
- Sigstore: sign the output bundle at `--book-publish`; public certificate available for verification.
- MarkLLM: inject statistical watermark into LLM generations at `WriterAgent` level.
- OML-1.0-Fingerprinting: embed ownership fingerprint in published text.
- Verification: `orchestrator --verify-provenance <book_file>` checks signatures.

**Key open questions.**
- Does MarkLLM watermarking degrade prose quality or voice consistency scores?
- Legal status of LLM watermarking in target publishing jurisdictions?
- Can watermarks survive editing by a human author (post-pipeline revision)?

**Estimated complexity.** M — library integrations; primary risk is prose quality impact.

*Source: Bunko §7–8.*

---

## V2.7 — Temporal Durable Execution

**Description.** Replace LangGraph checkpoint persistence with Temporal for very long runs (20+ books in a series).

**Prerequisites.**
- LangGraph checkpoint persistence proven insufficient for long runs (observable in V1 production).
- Temporal infrastructure available locally or on-prem.

**Design sketch.**
- Wrap each LangGraph run in a Temporal workflow.
- Temporal handles retry, durability, and long-running orchestration across process restarts.
- LangGraph continues to manage per-scene state graph; Temporal manages cross-scene and cross-book orchestration.

**Key open questions.**
- Is Temporal overkill for single-author V1 usage?
- Does V1 checkpoint persistence prove sufficient for 20-book series?
- Temporal local dev setup complexity vs value at V1 scale?

**Estimated complexity.** L — requires Temporal infrastructure, workflow wrapping of entire pipeline.

*Source: IMPLEMENTATION_PLAN.md Phase 15.*

---

## V2.8 — Additional Genre Modules

**Description.** Literary fiction, science fiction, fantasy, mystery genre profiles — each requiring a working author for validation before shipping.

**Prerequisites.**
- Romance Module v1.0 production-validated.
- At least one published book per target genre (for author validation).
- Per-genre SME review (equivalent of MBSE Craft Reviews for Romance).

**Design sketch.**
- Each genre module follows the same `genre_profile.schema.json` structure as `romance_module_v1.yaml`.
- Required elements: `scene_function_vocabulary`, `required_scene_slots`, `heat_scale` (if applicable), `structural_conventions`, `trope_library`.
- Literary fiction: no heat scale; emphasis on thematic resonance, interpretive depth.
- Science fiction: world-building ledger extension; technology-consistency checker in `BibleSteward`.
- Fantasy: magic-system consistency checker; world-building-heavy `BibleSteward` rules.
- Mystery: evidence ledger; fair-play constraint (all clues introduced before solution).

**Key open questions.**
- Who validates each genre module? (Literary/thriller SMEs identified in MBSE reviews.)
- How does the trope library differ structurally across genres?
- Should genre modules be community-contributed or author-controlled?

**Estimated complexity.** M per genre module; XL total for all 4.

*Source: IMPLEMENTATION_PLAN.md Phase 15 + MBSE Craft Reviews.*

---

## V2.9 — EvoSkill → Claude Dreaming Handoff

**Description.** If Claude Managed Agents "Dreaming" feature reaches GA and demonstrably outperforms EvoSkill for fiction-domain traces, wire it as the primary skill evolution mechanism.

**Prerequisites.**
- Dreaming feature available in production Anthropic API (not GA as of 2026-05-18).
- Comparative evaluation on ≥ 100 fiction failure traces: Dreaming vs EvoSkill.

**Design sketch.**
- `evoskill_client.py` already has `USE_DREAMING = False` feature flag and `_dreaming_propose_skill()` stub (from Task 012).
- Implement `_dreaming_propose_skill()` using Managed Agents Dreaming API when available.
- Evaluate on held-out fiction trace corpus: Dreaming skill quality vs EvoSkill skill quality.
- If Dreaming wins on ≥ 3 of 5 evaluation metrics: flip `USE_DREAMING = True`; deprecate EvoSkill nightly pass.

**Key open questions.**
- Dreaming API shape (not yet GA; watch Anthropic release notes).
- What are the 5 evaluation metrics for "skill quality" in fiction domain?
- Does Dreaming operate on traces in the same format as EvoSkill, or require reformatting?

**Estimated complexity.** S (if Dreaming API is drop-in compatible) to M (if reformatting required).

*Source: Bunko §5.5; IMPLEMENTATION_PLAN.md Phase 12 T12.6.*
