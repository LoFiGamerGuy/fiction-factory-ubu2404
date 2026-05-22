# Decision Gate: Claude Dreaming vs EvoSkill

**BCR ID:** BCR-20260522-claude-dreaming-mem0  
**Decision Location:** After Phase 7 smoke test (T7.1)  
**Status:** PENDING (to be decided after first real agent execution)  
**Date Created:** 2026-05-22

---

## Executive Summary

After Phase 7 WriterAgent smoke test, evaluate **Claude Managed Agents "Dreaming"** 
vs **EvoSkill nightly pass** as the primary self-improvement mechanism for the 
Fiction-Factory pipeline.

**Three possible outcomes:**
1. **Dreaming only** — Drop EvoSkill implementation
2. **EvoSkill only** — Disable Dreaming, use nightly batch learning
3. **Both** — Use Dreaming for real-time reflection + EvoSkill for meta-analysis

---

## Evaluation Criteria

### 1. Convergence Speed

**Metric:** Number of REVISE cycles to reach `Approved` state per scene.

**Method:**
- Run `tests/fixtures/dreaming_eval/` 3-scene fixture WITH Dreaming
- Run same fixture WITHOUT Dreaming
- Compare: average REVISE count per scene

**Decision threshold:**
- If Dreaming reduces REVISE count by ≥30% → strong signal for Dreaming
- If Dreaming increases REVISE count → strong signal for EvoSkill

**Logged in:** ConvergenceController routing decisions per scene

---

### 2. Prose Quality

**Metric:** `VoiceConsistencyMetric` score (DeepEval custom metric from Phase 14).

**Method:**
- Evaluate final scene output against voice profile
- Score range: 0.0 (inconsistent) to 1.0 (perfect match)
- Compare: WITH vs WITHOUT Dreaming

**Decision threshold:**
- If Dreaming improves VoiceConsistencyMetric by ≥0.05 → strong signal for Dreaming
- If scores are within 0.02 → neutral

**Logged in:** `data/eval_results/voice_consistency_{with|without}_dreaming.json`

---

### 3. Routing Decision Count

**Metric:** Total routing decisions (GO / REVISE / RE-PLAN / FORCE-RESOLVE) across 3 scenes.

**Method:**
- Count ConvergenceController routing calls per run
- Compare: WITH vs WITHOUT Dreaming

**Decision threshold:**
- Fewer routing decisions = more efficient convergence
- If Dreaming reduces routing count by ≥20% → strong signal for Dreaming

**Logged in:** ConvergenceController audit log per scene

---

## Additional Considerations

### Infrastructure Burden

**Dreaming:**
- Zero infrastructure (built into Claude API)
- No scheduling, no separate processes
- Per-agent persistent memory (filesystem-backed)

**EvoSkill:**
- Requires nightly cron job or manual trigger
- Proposer/Evaluator/Frontier loop
- Per-series git namespacing
- Promotion workflow to WUPHF wiki

**Weight:** Favor simpler if outcomes are equivalent.

---

### Complementarity

**Are they complementary?**
- **Dreaming:** Real-time, per-agent, session-to-session learning
- **EvoSkill:** Meta-level, cross-agent, pattern synthesis

**Potential synergy:**
- Dreaming improves individual agent strategies
- EvoSkill identifies recurring failure modes across agents
- Both together may be stronger than either alone

**Decision:** If both show positive signals, evaluate "Both" outcome.

---

## Decision Process

### Phase 7 T7.1 Evaluation Run

1. Run `pytest tests/fixtures/dreaming_eval/ --with-dreaming`
2. Run `pytest tests/fixtures/dreaming_eval/ --without-dreaming`
3. Collect all 3 metrics (convergence speed, prose quality, routing decisions)
4. Generate comparison report: `scripts/compare_dreaming_runs.py`

### Review and Decide

**Reviewer:** User (project owner)

**Decision recorded in:** `DECISIONS.md` as DEC-007-001

**Options:**

| Outcome | Trigger Condition | Implementation Action |
|---------|-------------------|----------------------|
| **(1) Dreaming only** | Dreaming outperforms EvoSkill on ≥2/3 metrics by decision thresholds | Phase 12 EvoSkill implementation marked DEFERRED. ManagedAgentConfig defaults to `dreaming_enabled=True`. |
| **(2) EvoSkill only** | EvoSkill outperforms Dreaming on ≥2/3 metrics | ManagedAgentConfig defaults to `dreaming_enabled=False`. Phase 12 EvoSkill proceeds as planned. |
| **(3) Both** | Mixed results OR both show strong positive signals | Both enabled by default. Document complementarity in ARCHITECTURE.md. |

---

## Rollback Plan

If chosen approach proves unsatisfactory after 50+ production scenes:

**Fallback:** Re-run this decision gate with production trace data.

**Re-evaluation criteria:**
- Same 3 metrics, but on production corpus (not fixture)
- Trigger: >30% of scenes require RE-PLAN routing
- OR: VoiceConsistencyMetric drops below 0.70 threshold

---

## Test Execution Checklist

- [ ] Phase 7 smoke test passes (T7.9 acceptance)
- [ ] WriterAgent wired to ManagedAgentConfig
- [ ] `--with-dreaming` and `--without-dreaming` paths executable
- [ ] ConvergenceController logging routing decisions
- [ ] VoiceConsistencyMetric implemented (Phase 14 T14.1)
- [ ] `scripts/compare_dreaming_runs.py` generates comparison report
- [ ] User reviews report and makes decision
- [ ] Decision logged in `DECISIONS.md` as DEC-007-001

---

## References

- BCR-20260522-claude-dreaming-mem0 (APPROVED 2026-05-22)
- `tests/fixtures/dreaming_eval/` (T1.14)
- `IMPLEMENTATION_PLAN.md` Phase 7 T7.1, T7.9
- `ARCHITECTURE.md` §Layer 9 — Skill Evolution (EvoSkill)
- Claude Managed Agents documentation (Anthropic)
- EvoSkill: `github.com/sentient-agi/EvoSkill`

---

## Approval

**Status:** Template created 2026-05-22 (T1.15)  
**Decision:** PENDING — to be completed after Phase 7 smoke test

**Decision signature line (to be filled after evaluation):**
```
DECISION: [Dreaming only | EvoSkill only | Both]
DECIDED: [Date]
RATIONALE: [Brief summary of evaluation results]
APPROVED: [User]
```
