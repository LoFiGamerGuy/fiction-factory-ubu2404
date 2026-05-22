# Dreaming Evaluation Fixture

**BCR-20260522-claude-dreaming-mem0 (T1.14)**

## Purpose

3-scene Romance Module fixture for comparing agent performance WITH vs WITHOUT
Claude Managed Agents Dreaming feature enabled.

## Scenes

1. **Meet-cute** — First encounter between protagonists
2. **First-date** — Initial romantic tension
3. **First-conflict** — Obstacle that tests the relationship

## Evaluation Criteria (Phase 7 Decision Gate)

Per `docs/bcr-decisions/dreaming-vs-evoskill.md`:

1. **Convergence speed** — How many REVISE cycles to reach Approved state?
2. **Prose quality** — VoiceConsistencyMetric score
3. **Routing decision count** — Total GO/REVISE/RE-PLAN/FORCE-RESOLVE decisions

## Usage

```bash
# Run smoke test WITH Dreaming
pytest tests/fixtures/dreaming_eval/ --with-dreaming

# Run smoke test WITHOUT Dreaming
pytest tests/fixtures/dreaming_eval/ --without-dreaming

# Compare results
python scripts/compare_dreaming_runs.py
```

## Fixture Files

- `romance_series_spec.yaml` — Series-level spec
- `book_spec.yaml` — Book-level spec
- `scene_01_meet_cute.yaml` — Scene 1 spec
- `scene_02_first_date.yaml` — Scene 2 spec
- `scene_03_first_conflict.yaml` — Scene 3 spec
- `test_dreaming_harness.py` — Test runner

## Agents Not Wired Yet

This fixture is infrastructure-only (Phase 1). Agents are wired in Phase 7 T7.1
after WriterAgent is fully implemented.

**Acceptance:** Harness runs without errors (agents not wired yet).
