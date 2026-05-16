# Task 012 — Skill Evolution (EvoSkill)

```
status: pending
started:
completed:
phase: 12
estimated_hours: 8-12
depends_on: task-011
```

## Goal

EvoSkill integrated for per-series skill learning from production traces. Fiction-domain failure/success trace definitions. Per-series namespace in EvoSkill's git-branch versioning. Nightly skill evolution pass. Approved skills promoted to WUPHF `series-bible` wiki as editorial guidelines.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 12 (Skill Evolution)

## Dependencies

- task-011 (WUPHF wiki — skill promotion target; ROMA client available)
- task-007 (scene state machine — traces collected after each finalized scene)
- task-008 (specialist agent outputs — included in traces)

## Acceptance criteria

- [ ] `pipeline/evoskill/trace_collector.py` — collects scene traces (agent inputs, outputs, routing decisions, quality scores) formatted for EvoSkill Proposer
- [ ] Fiction-domain trace definitions: failure trace = scene where a downstream critic scores below threshold OR QualityAgent routes to REVISE/RE-PLAN; success trace = scene that reached FINAL without REVISE
- [ ] Per-series namespace: EvoSkill git-branch versioning at `series/{series_id}/skills/`; traces and skills for different series are isolated
- [ ] `pipeline/evoskill/evoskill_client.py` — wraps EvoSkill Proposer/Evaluator/Frontier API
- [ ] Nightly EvoSkill pass: Proposer analyzes failure traces, classifies error mode, proposes candidate skill
- [ ] Evaluator benchmarks candidate skill on fixture corpus
- [ ] Frontier Pareto-keeps best variants (discards dominated candidates)
- [ ] Skill promotion: approved skills written to WUPHF `series-bible` wiki as editorial guidelines page
- [ ] Claude "Dreaming" feature hook: if Dreaming reaches GA, `evoskill_client.py` has a documented switchover path (comment block + feature flag)
- [ ] Integration test: inject fixture failure trace → EvoSkill Proposer generates candidate skill → Frontier keeps it (mock Evaluator with pass) → skill promoted to WUPHF wiki
- [ ] Per-series namespace isolation test: skills for series_A not visible to series_B
- [ ] `make test` passes

## Subtasks

- T12.1 — Define fiction-domain trace schema `schemas/evoskill/trace.schema.json`: `trace_id`, `series_id`, `book_id`, `scene_id`, `trace_type` (enum: failure/success), `failure_mode` (enum: voice_drift/pacing_violation/continuity_error/heat_curve_miss/quality_gate_fail/null for success), `agent_inputs` (dict: agent_id → input hash), `agent_outputs` (dict: agent_id → output hash), `routing_decisions` (list of ConvergenceDecision), `quality_scores` (dict: metric_id → float), `critic_scores` (dict: agent_id → score), `word_count`, `timestamp`.
- T12.2 — Implement `pipeline/evoskill/trace_collector.py`. TraceCollector: `collect_scene_trace(job_context: JobContext, scene_result: SceneResult) → Trace`. Classification logic: (1) If any QualityAgent routing_decision == REVISE or RE-PLAN → failure trace, failure_mode = quality_gate_fail. (2) If any critic score below threshold (from quality_gates in genre_profile) → failure trace, failure_mode = critic-specific. (3) Otherwise → success trace. `save_trace(trace: Trace)`: write to `data/{series_id}/traces/{scene_id}.json`. `get_failure_traces(series_id: str, since: datetime) → list[Trace]`.
- T12.3 — Integrate TraceCollector into job_runner: after each finalized scene (after LedgerManager update), call `trace_collector.collect_scene_trace(job_context, scene_result)`.
- T12.4 — Implement `pipeline/evoskill/evoskill_client.py`. EvoSkillClient: wraps EvoSkill Proposer/Evaluator/Frontier API (sentient-agi/EvoSkill). `propose_skill(failure_traces: list[Trace], series_id: str) → CandidateSkill`: call EvoSkill Proposer; returns proposed skill (natural language editorial guideline with associated condition). `evaluate_skill(candidate: CandidateSkill, benchmark_corpus: list[Trace]) → EvalResult`: call Evaluator; returns score vs baseline. `update_frontier(candidate: CandidateSkill, eval_result: EvalResult) → bool`: call Frontier; returns True if candidate is kept (Pareto-dominates an existing skill). Per-series namespace: all EvoSkill API calls include `branch: f"series/{series_id}/skills/"`.
- T12.5 — Implement nightly EvoSkill pass: `scripts/evoskill_nightly.py`. Steps: (1) Load failure traces from last 24h for each active series. (2) Call `evoskill_client.propose_skill(failure_traces, series_id)`. (3) Call `evoskill_client.evaluate_skill(candidate, fixture_benchmark_corpus)`. (4) Call `evoskill_client.update_frontier(candidate, eval_result)`. (5) If kept: call `wuphf_client.update_wiki(f"editorial-guidelines/{series_id}", skill_to_markdown(candidate))`. Schedule: cron job at 02:00 local time (document in `runbooks/evoskill-setup.md`). For V1: run manually via `python scripts/evoskill_nightly.py` — cron setup is optional.
- T12.6 — Implement skill promotion to WUPHF wiki: `pipeline/evoskill/skill_promoter.py`. `promote_to_wiki(skill: CandidateSkill, series_id: str)`: convert skill to markdown (editorial guideline format: condition, recommendation, example_failure, example_success); call `wuphf_client.update_wiki(f"editorial-guidelines/{series_id}/{skill.skill_id}", markdown)`. Skills accumulate as a library of per-series guidelines.
- T12.7 — Add Claude "Dreaming" feature flag: in `evoskill_client.py`, add `USE_DREAMING = False` feature flag at top of file. Comment block: "If Claude Managed Agents 'Dreaming' feature reaches GA and produces better per-series improvements than EvoSkill nightly pass, flip USE_DREAMING = True and implement _dreaming_propose_skill() below. See IMPLEMENTATION_PLAN.md Phase 12 T12.6 for evaluation criteria." Leave `_dreaming_propose_skill()` as a stub method that raises NotImplementedError.
- T12.8 — Write integration test `tests/integration/test_evoskill.py`: (1) Create fixture failure trace (voice_drift failure_mode). (2) Call `evoskill_client.propose_skill([fixture_trace], "test_series")` (mock EvoSkill API — return plausible skill). (3) Call `evaluate_skill` (mock Evaluator — return passing eval). (4) Call `update_frontier` (mock Frontier — return True / kept). (5) Call `skill_promoter.promote_to_wiki` (mock WUPHF — verify `update_wiki` called with correct page and markdown). (6) Assert all steps succeed without error.
- T12.9 — Write namespace isolation test: `test_series_namespace_isolation()`: traces and skills for "series_A" stored at different path prefix than "series_B"; skills fetched for series_A do not include series_B skills.
- T12.10 — Commit: `feat(evoskill): EvoSkill fiction-domain trace adaptation, per-series namespacing, WUPHF skill promotion (task-012)`.

## Key decisions that affect this task

- **EvoSkill is confirmed real (decisions.md 2026-05-15):** `sentient-agi/EvoSkill`. Read the actual repo before implementing the client wrapper.
- **Per-series namespace (decisions.md):** Skill contamination between series would corrupt voice. Series namespace is a hard isolation requirement.
- **Failure trace definition for fiction domain:** The fiction-specific failure/success classification (REVISE routing, critic threshold misses) is the key adaptation that makes EvoSkill work for this domain.
- **Skill promotion to WUPHF wiki:** Promoted skills become editorial guidelines — human-readable, git-versioned, part of the series bible. The author can read and audit them.
- **Claude Dreaming as potential future replacement (decisions.md 2026-05-15):** Monitor — if it reaches GA and outperforms EvoSkill for fiction traces, swap. Feature flag keeps this switchover clean.
- **No auto-add of generated content (DEC-003):** EvoSkill skills are guidelines, not prose. The prohibition on retaining generated prose does not apply to the skills themselves (they are rules/observations, not prose samples).

## Suggested approach

1. Define trace schema; implement TraceCollector; integrate into job_runner.
2. Implement EvoSkillClient with mock backend for testing.
3. Implement nightly pass script.
4. Implement SkillPromoter + WUPHF wiki promotion.
5. Add Dreaming feature flag stub.
6. Write integration test with all mocked API backends.
7. Run `make test`.
8. Commit.

## Decisions to log in DECISIONS.md

- Fixture benchmark corpus for Evaluator (use fixture traces from smoke test — log this choice).
- EvoSkill API surface used (Proposer/Evaluator/Frontier — document actual API method names after reading the repo).
- Nightly pass scheduling (manual for V1; cron for production).
- Pareto-keep threshold (document Frontier's retention criterion).

## Notes

- Read `sentient-agi/EvoSkill` README and API before implementing `evoskill_client.py`. The API shape is not fully documented in the bundles.
- The nightly pass script (`scripts/evoskill_nightly.py`) is the mechanism for continuous improvement. V1 runs it manually. V2 automates via cron or Prefect.
- Skills promoted to WUPHF wiki are human-readable editorial guidelines (e.g., "When heat_curve is at position > 0.5 and last 3 scenes had dialogue_ratio > 0.6, prioritize action beats to avoid pacing stall"). The author reads these and decides whether to accept them into the authorial canon.
- The mock EvoSkill backend in tests must have the same method signatures as the real client — not just `MagicMock()`. Define a `MockEvoSkillBackend` class.

## Out of scope

- Drafter D fine-tuning (V2 roadmap — Phase 15)
- Reception tier (V2 roadmap)
- harbor eval (V2 roadmap — replaces DeepEval at scale)
- Ensemble drafting (V2 roadmap)
