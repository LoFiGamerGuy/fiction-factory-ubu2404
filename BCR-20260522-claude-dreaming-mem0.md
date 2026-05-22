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
