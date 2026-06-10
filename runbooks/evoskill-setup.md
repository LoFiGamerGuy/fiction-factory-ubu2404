# EvoSkill Setup and Nightly Operation

**Phase 12 deliverable - V1 local nightly pass runbook**

---

## Overview

EvoSkill learns from scene execution traces to accumulate per-series editorial skills. The pipeline automatically collects traces during normal operation. This runbook covers manual nightly invocation and optional cron automation.

**V1 mode:** Local mock by default. Proposer/Evaluator/Frontier run in stub mode with deterministic scoring when `EVOSKILL_API_URL` is not configured.

---

## Architecture Summary

```
Scene execution -> JobRunner collects trace -> saves to data/{series_id}/traces/

Nightly pass:
  1. TraceCollector.get_failure_traces(series_id, since=yesterday)
  2. EvoSkillClient.propose_skill(failure_traces) -> CandidateSkill
  3. EvoSkillClient.evaluate_skill(candidate, fixture_corpus) -> EvalResult
  4. EvoSkillClient.update_frontier(candidate, eval_result) -> bool (kept?)
  5. SkillPromoter.promote_to_wiki(candidate, series_id) -> markdown skill
```

**Trace classification:**
- `failure/continuity_error` - bible_contradiction=True
- `failure/pacing_violation` - overdue_promises present
- `failure/quality_gate_fail` - routing_decisions contain REVISE or RE_PLAN
- `success` - all gates passed, routing_decision=GO

**Skill promotion:** Approved skills -> `{data_root}/{series_id}/skills/{skill_id}.md` and, when WUPHF is configured, `series-bible/{series_id}/editorial-guidelines/{skill_id}`.

---

## Prerequisites

**Phase 1 dependencies installed:**
```bash
# Already in uv environment from T1.10.
# EvoSkillClient also runs in local mock mode when no remote API is configured.
```

**Data layout:**
```
data/
  {series_id}/
    traces/          # Auto-populated by JobRunner after each scene
      {scene_id}.json
    skills/          # Written by SkillPromoter after nightly pass
      {skill_id}.md
```

**No external service required for V1.** EvoSkillClient operates in mock mode when `api_url=None`. WUPHF promotion is enabled only when `WUPHF_WIKI_ROOT` is set or `WUPHF_API_URL` and `WUPHF_API_KEY` are both set.

---

## Manual Nightly Invocation

### Option 1: Existing CLI Script

The repository includes `scripts/evoskill_nightly.py`, which scans all series under the configured data root and processes failure traces from the last 24 hours.

```bash
python scripts/evoskill_nightly.py --data-root data
```

The script logs the number of failure traces found, proposed skills, evaluation scores, frontier decisions, and promotion status. `--data-root` controls where local skill markdown is written.

---

### Option 2: Python REPL

```python
from datetime import UTC, datetime, timedelta
from pathlib import Path
from pipeline.evoskill.evoskill_client import EvoSkillClient
from pipeline.evoskill.skill_promoter import SkillPromoter
from pipeline.evoskill.trace_collector import TraceCollector

# Configuration
SERIES_ID = "my-romance-series"
DATA_ROOT = Path("data")

# Step 1: Collect failure traces from last 24 hours
collector = TraceCollector(data_root=DATA_ROOT)
since = datetime.now(UTC) - timedelta(days=1)
failure_traces = collector.get_failure_traces(SERIES_ID, since=since)

print(f"Found {len(failure_traces)} failure traces for {SERIES_ID}")

if not failure_traces:
    print("No failures to learn from. Exiting.")
    exit(0)

# Step 2: Propose skill (mock mode: api_url=None)
client = EvoSkillClient(api_url=None, api_key=None)
candidate = client.propose_skill(failure_traces, series_id=SERIES_ID)

print(f"Proposed skill: {candidate.skill_id}")
print(f"  Failure mode: {candidate.failure_mode}")
print(f"  Condition: {candidate.condition}")
print(f"  Recommendation: {candidate.recommendation}")

# Step 3: Evaluate skill (mock fixture corpus)
eval_result = client.evaluate_skill(candidate, failure_traces)

print(f"Evaluation: passed={eval_result.passed}, improvement={eval_result.improvement:.2f}")

# Step 4: Update frontier (Pareto-keep logic)
kept = client.update_frontier(candidate, eval_result)

if not kept:
    print("Skill not kept (dominated by existing frontier). Exiting.")
    exit(0)

print(f"Skill kept on frontier.")

# Step 5: Promote to local file, and optionally WUPHF when configured
promoter = SkillPromoter(wuphf_client=None, data_root=DATA_ROOT)
promoter.promote_to_wiki(candidate, series_id=SERIES_ID)

skill_path = DATA_ROOT / SERIES_ID / "skills" / f"{candidate.skill_id}.md"
print(f"Skill promoted to: {skill_path}")
```

## Cron Automation (Optional)

**V1 note:** Manual invocation is the Phase 12 acceptance criterion. Cron automation is documented here for V2 operational setup.

### Crontab Entry

Run nightly at 2:00 AM for all active series:

```cron
0 2 * * * cd /path/to/workspace && python scripts/evoskill_nightly.py --data-root data >> logs/evoskill.log 2>&1
```

The existing CLI scans every active series under `--data-root`, so a separate multi-series wrapper is not needed for V1.

---

## Monitoring and Logs

**Trace volume per series:**
```bash
# Count traces in last 24 hours
find data/my-romance-series/traces/ -name "*.json" -mtime -1 | wc -l
```

**Failure rate:**
```bash
# Count failure traces
python -c "
from pipeline.evoskill.trace_collector import TraceCollector
from pathlib import Path
collector = TraceCollector(Path('data'))
failures = collector.get_failure_traces('my-romance-series')
print(f'{len(failures)} failure traces')
"
```

**Skill accumulation:**
```bash
ls -lh data/my-romance-series/skills/
```

**Review a skill:**
```bash
cat data/my-romance-series/skills/skill-abc123.md
```

---

## V2 Roadmap (Deferred)

| Feature | Status |
|---|---|
| **Production API integration** | V2 - requires hosted EvoSkill service |
| **Claude Dreaming comparison** | Decision gate after Phase 7 smoke test (DEC-007-001) |
| **Automated skill application** | V2 - requires ContextPackBuilder skill injection |
| **Skill regression testing** | V2 - requires production corpus |
| **Cross-series meta-learning** | V2 - requires 10+ series in production |

---

## Troubleshooting

**No traces saved after scene run:**
- Check `JobRunner` log for trace collection warnings
- Verify `data/{series_id}/traces/` directory exists and is writable
- Confirm `trace_collector` parameter is not explicitly disabled

**Nightly pass finds no failures:**
- Normal for stable production runs
- Adjust `lookback_days` to capture longer windows
- Check if traces were classified as `success` (view JSON files directly)

**Skill promotion fails:**
- Verify `data/{series_id}/skills/` directory is writable
- Check for filesystem permission issues
- Review `SkillPromoter` log output

**ImportError during nightly run:**
- Confirm `uv sync` has run and all Phase 1 dependencies are installed
- Verify Python path includes `pipeline/` package root

---

## Decision Log

- **DEC-007-001** (2026-05-22) - Both Claude Dreaming and EvoSkill retained in V1. Dreaming provides session continuity; EvoSkill provides cross-agent meta-learning. Complementary, not competing.
- **T012-002** (2026-05-18) - Manual nightly invocation is V1 scope. Cron automation deferred to V2 operational setup.

---

## References

- `IMPLEMENTATION_PLAN.md` Phase 12 - EvoSkill integration
- `tests/integration/test_evoskill.py` - Full fixture test coverage
- `pipeline/evoskill/trace_collector.py` - Trace classification logic
- `pipeline/evoskill/evoskill_client.py` - Propose/Evaluate/Frontier API
- `pipeline/evoskill/skill_promoter.py` - Wiki promotion logic
- `ARCHITECTURE.md` Layer 9 - Skill Evolution (EvoSkill)

---

**Last updated:** 2026-06-09
**Phase:** 12 (EvoSkill)
**Status:** Manual nightly invocation operational; cron automation optional
