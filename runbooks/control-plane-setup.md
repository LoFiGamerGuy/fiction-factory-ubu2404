# Control-Plane Setup Runbook

Covers initial configuration of the three external collaboration services used
by the fiction-factory pipeline: **Paperclip** (budget tracking), **WUPHF**
(workspace messaging + wiki), and **ROMA** (narrative decomposition).

---

## Environment Variables

Add the following to your `.env` file (a `.env.example` is provided in the
project root with placeholder values):

```dotenv
# ── Paperclip ──────────────────────────────────────────────────────────────────
PAPERCLIP_API_URL=https://your-paperclip-instance/api/v1
PAPERCLIP_API_KEY=pk_live_XXXXXXXXXXXXXXXXXXXX

# ── WUPHF ─────────────────────────────────────────────────────────────────────
WUPHF_API_URL=https://your-wuphf-instance/api/v1
WUPHF_API_KEY=wk_live_XXXXXXXXXXXXXXXXXXXX

# ── ROMA ──────────────────────────────────────────────────────────────────────
ROMA_API_URL=https://your-roma-instance/api/v1
ROMA_API_KEY=rk_live_XXXXXXXXXXXXXXXXXXXX
```

All three clients use `python-dotenv` (`load_dotenv()`) and fall back to
graceful-degradation mode when any of these variables is absent — the pipeline
continues without external tracking or approvals.

---

## 1. Paperclip — Budget Configuration

### 1.1 Create agent-role budgets

In the Paperclip admin UI (or via its management API), create one budget entry
per agent role with the monthly limits below:

| Agent role    | Monthly budget |
|---------------|---------------|
| `writer`      | $15.00        |
| `editor`      | $5.00         |
| `quality`     | $3.00         |
| `specialist`  | $5.00         |
| `orchestrator`| $2.00         |

The role names correspond to the `agent_role` strings passed to
`PaperclipClient.check_budget()` and `PaperclipClient.record_cost()`.

### 1.2 Approval gates

The following gate names are used by `PaperclipClient.request_approval()`:

| Gate name             | Triggered by                         |
|-----------------------|--------------------------------------|
| `phase_end_0`         | End of Phase 0 (tooling install)     |
| `synthesis_shape_2_1` | §2.1.6 early synthesis scoping       |
| `synthesis_shape_2_4` | §2.4 final binding synthesis shape   |
| `tooling_decisions`   | End of Phase 3 — TOOLING_DECISIONS   |
| `implementation_plan` | End of Phase 4 — IMPLEMENTATION_PLAN |

Configure any required approvers in Paperclip's gate settings so notifications
reach the right people.

### 1.3 Verify Paperclip

```bash
python - <<'EOF'
from pipeline.control.paperclip_client import PaperclipClient
c = PaperclipClient()
print("heartbeat:", c.heartbeat())
print("writer budget ok:", c.check_budget("writer"))
EOF
```

Expected output (when configured):
```
heartbeat: True
writer budget ok: True
```

---

## 2. WUPHF — Workspace Configuration

### 2.1 Create channels

Create these channels in your WUPHF workspace:

| Channel slug  | Purpose                                              |
|---------------|------------------------------------------------------|
| `pipeline`    | Operational status, scene completions, error alerts  |
| `drafts`      | Scene draft notifications, revision rounds           |

The `channel` argument to `WUPHFClient.post_to_channel()` must match these
slugs exactly.

### 2.2 Create wiki pages

Seed the following wiki pages before the first run:

| Page slug       | Purpose                                         |
|-----------------|-------------------------------------------------|
| `series-bible`  | Canonical series continuity and world-building  |
| `style-guide`   | Voice axes, prose style rules                   |
| `scene-tracker` | Live scene completion status                    |

Pages are created/updated via `WUPHFClient.update_wiki(page, content)`.

### 2.3 Verify WUPHF

```bash
python - <<'EOF'
from pipeline.control.wuphf_client import WUPHFClient
c = WUPHFClient()
c.post_to_channel("pipeline", "Control-plane setup verification ping")
c.update_wiki("series-bible", "# Series Bible\n\nInitial content — replace me.")
content = c.read_wiki("series-bible")
print("wiki read back:", content[:40])
EOF
```

---

## 3. ROMA — Narrative Decomposition

### 3.1 Instance configuration

ROMA (sentient-agi/ROMA) requires an API endpoint and key.  For local-only v1
deployments, leave `ROMA_API_URL` and `ROMA_API_KEY` **unset**; `ROMAClient`
will automatically fall back to the built-in `BookStructurePlanner` so no ROMA
instance is needed.

When a ROMA instance is available:
1. Set `ROMA_API_URL` to the base URL (e.g. `http://localhost:8080/api/v1`).
2. Set `ROMA_API_KEY` to the bearer token issued by ROMA's admin interface.

### 3.2 Verify ROMA (or fallback)

```bash
python - <<'EOF'
from pipeline.control.roma_client import ROMAClient
c = ROMAClient()
spec = {
    "series_id": "test-series",
    "genre_config": {"chapter_count": 6, "word_count_target": 10000, "heat_curve": "rising"},
    "books": [{"book_id": "test-book-001", "chapter_count": 6, "scenes_per_chapter": 2}],
}
plan = c.decompose(spec)
print("series_id:", plan.series_id)
print("book_plans:", len(plan.book_plans))
result = c.verify(plan)
print("valid:", result.valid, "errors:", result.errors)
EOF
```

---

## 4. Heartbeat Schedule

The pipeline should poll Paperclip's `/health` endpoint every 5 minutes to
confirm the control plane is reachable.  Configure this in your process
manager or scheduler:

```cron
# Poll Paperclip heartbeat every 5 minutes
*/5 * * * * cd /path/to/fiction-factory && python -c "
from pipeline.control.paperclip_client import PaperclipClient
import sys
ok = PaperclipClient().heartbeat()
sys.exit(0 if ok else 1)
" >> /var/log/fiction-factory/heartbeat.log 2>&1
```

For local development, a simple loop is sufficient:

```bash
while true; do
    python -c "from pipeline.control.paperclip_client import PaperclipClient; PaperclipClient().heartbeat()"
    sleep 300
done
```

---

## 5. Full Verification Checklist

Run through this checklist after initial setup:

- [ ] `.env` file created with all six env vars (URL + key for each service)
- [ ] `python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.environ.get('PAPERCLIP_API_URL'))"` prints the correct URL
- [ ] Paperclip heartbeat returns `True`
- [ ] All five agent-role budgets visible in Paperclip UI
- [ ] `pipeline` and `drafts` channels exist in WUPHF
- [ ] `series-bible` wiki page readable via `WUPHFClient.read_wiki()`
- [ ] `ROMAClient().decompose(spec)` returns a `DecomposedPlan` (ROMA or fallback)
- [ ] Heartbeat cron/loop running and logging to expected path
- [ ] Integration tests pass: `pytest tests/integration/test_control_collaboration.py -v`
