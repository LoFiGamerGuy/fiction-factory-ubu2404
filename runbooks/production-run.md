# Production Run Runbook

Full sequence for producing a book with the fiction-factory V1 pipeline.

---

## Prerequisites

1. Virtual environment active: `source .venv/bin/activate`
2. `.env` file present with required keys (copy from `.env.example` and fill in values)
3. Mem0 running locally (optional — pipeline degrades gracefully without it):
   ```
   docker run -p 8888:8000 mem0ai/mem0
   ```
4. Series spec YAML prepared at `data/series/{series_id}/spec.yaml`

---

## Step 1 — Validate series spec

```bash
python -m pipeline.orchestrator --validate-spec data/series/{series_id}/spec.yaml
```

Expected output: `OK: data/series/.../spec.yaml is valid`

---

## Step 2 — Init series (ROMA decomposition + Paperclip approval)

```bash
python -m pipeline.orchestrator --init-series data/series/{series_id}/spec.yaml
```

This runs:
- `--validate-spec`
- Paperclip `request_approval("series_sign_off", ...)` — pauses up to 1 hour for human approval
- ROMA `decompose(series_spec)` → book plans for each book
- Posts plan summary to WUPHF `pipeline` channel

Approve via the Paperclip UI within 1 hour or the pipeline times out.

---

## Step 3 — Seed Mem0 (optional)

If Mem0 is running:

```python
from pipeline.memory.mem0_client import Mem0Client
client = Mem0Client()
client.seed_series("my-series", ["Voice: first-person intimate...", "Character: ..."])
```

---

## Step 4 — Upload series bible to Claude Files API (optional)

Reduces per-call token cost for long series. One-time per series:

```python
from pipeline.memory.files_api_client import FilesAPIClient
from pathlib import Path
fc = FilesAPIClient()
fc.upload_series_bible(Path("data/series/my-series/bible.md"), "my-series")
```

File IDs are stored in `data/my-series/file_ids.json`.

---

## Step 5 — Init book

```bash
python -m pipeline.orchestrator --init-book {series_id} {book_number}
```

This runs:
- Paperclip `request_approval("spec_sign_off", spec_summary)` — 1-hour window
- `BookStructurePlanner.plan()` → writes `scene_inventory.json`

Expected output: `Initialized book 'book01': N scenes planned.`

---

## Step 6 — Run scenes

Run each scene in sequence:

```bash
# For a book with N scenes, loop through scene IDs from scene_inventory.json
for scene_id in $(jq -r '.scenes[].scene_id' data/series/{series_id}/book01/scene_inventory.json); do
    python -m pipeline.orchestrator --job $scene_id
done
```

Monitor via Author Dashboard:
```bash
make dashboard
# Open http://localhost:3000
```

Each scene writes to:
- `data/books/{book_id}/scenes/{scene_id}.md` — final prose
- `data/{book_id}/quality_gate_history.jsonl` — gate decisions
- All 10 ledger JSONL files

---

## Step 7 — Verify book

```bash
python -m pipeline.orchestrator --verify-book {book_id} {series_id}
```

Expected output: `PASSED: book 'book01' passed all structural checks.`

Fix any failures before publishing.

---

## Step 8 — Run eval metrics

```bash
make eval
```

Check `data/eval_results.json` for scores:
- `VoiceConsistencyMetric` ≥ 0.75 (romance) / 0.70 (erotica)
- `AITellMetric` ≥ 0.50

---

## Step 9 — Publish

```bash
python -m pipeline.orchestrator --book-publish {book_id} {series_id}
```

This runs verify-book, then:
- Copies `manuscript.md` → `output/{book_id}/manuscript.md`
- Writes `output/{book_id}/generation_report.json`
- Triggers Paperclip `request_approval("manuscript_sign_off", ...)` — 1-hour window

---

## Model tier: switching to production

**Default (test tier):** Uses cheaper/faster models for development.

To run a production-quality comparison:

1. Edit `model_router.json`: set `"model_tier": "production"`
2. Run the 3-scene integration test:
   ```bash
   python -m pytest tests/integration/test_3scene_integration.py -v
   ```
3. Log comparison results in `DECISIONS.md`
4. Revert to `"model_tier": "test"` unless committing to production cost

Production models: Sonnet 4.6 (drafter), Opus 4.7 (critics/editors).

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| Budget exceeded for {role} | Paperclip monthly budget hit | Increase budget in Paperclip config or wait for reset |
| Approval gate timed out | No human action in 1 hour | Re-run the command; approve promptly |
| `scene_inventory.json` not found | `--init-book` not run | Run `--init-book` first |
| `make eval` fails — no deepeval | deepeval not installed | `uv pip install -e ".[dev]"` |
| Mem0 unavailable | Docker not running | Start Mem0 container or ignore (graceful degradation) |
