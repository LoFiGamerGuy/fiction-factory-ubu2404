# Task 011 — Control + Collaboration Layer

```
status: pending
started:
completed:
phase: 11
estimated_hours: 8-12
depends_on: task-010
```

## Goal

Paperclip (control plane: budget enforcement, approval gates, heartbeat), WUPHF (collaboration: series-bible wiki, pipeline channel, audit log), and ROMA (recursive decomposition: series → book → act → chapter → scene planning) integrated into the pipeline. LangGraph continues to manage per-scene execution state; ROMA drives the planning phase.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 11 (Control + Collaboration Layer)

## Dependencies

- task-010 (orchestrator CLI — Paperclip approval gates wrap `--init-book` and `--book-publish`; WUPHF wiki sources series spec)
- task-009 (BibleSteward — WUPHF wiki sync targets bible events)
- task-003 (LedgerManager — Paperclip cost recording reads from cost_log.jsonl)

## Acceptance criteria

- [ ] `pipeline/control/paperclip_client.py` — `check_budget(agent_role: str) → bool`, `record_cost(agent_role: str, cost_usd: float)`, `request_approval(gate_name: str, context: dict) → bool`, `heartbeat() → bool`
- [ ] Paperclip: monthly token/dollar budgets configured per agent role (writer, editor, quality, specialist, orchestrator)
- [ ] Paperclip: approval gate before `--init-book` (spec sign-off); approval gate before `--book-publish` (manuscript sign-off)
- [ ] Paperclip: pipeline halts (orchestrator exits) if `check_budget()` returns False
- [ ] Paperclip: heartbeat schedule configured; pipeline health check accessible
- [ ] `pipeline/control/wuphf_client.py` — `post_to_channel(channel: str, message: str)`, `update_wiki(page: str, content: str)`, `read_wiki(page: str) → str`, `get_activity_stream(since: datetime) → list[ActivityEvent]`
- [ ] WUPHF workspace: `series-bible` wiki (git-backed markdown), `pipeline` channel (production rooms per book), `drafts` channel (agent drafts), activity stream (audit log of all agent actions)
- [ ] WUPHF → git sync: BibleSteward `commit_delta` also calls `wuphf_client.update_wiki()` to sync character cards, world facts, voice profile to `series-bible` wiki
- [ ] WUPHF series spec: series spec is the source of truth in WUPHF wiki; `--validate-spec` can read it from wiki via `wuphf_client.read_wiki()`
- [ ] ROMA integration: `pipeline/control/roma_client.py` — ROMA Atomizer/Planner/Executor/Aggregator/Verifier used for series → book → act → chapter → scene decomposition in `--init-series` command
- [ ] ROMA decomposes fixture series spec into a book plan without errors
- [ ] Integration test: ROMA decomposes series → book plan; Paperclip records cost; WUPHF wiki receives update
- [ ] `make test` passes

## Subtasks

- T11.1 — Configure Paperclip (already running from Phase 1 T1.11). Set monthly budgets per agent role: `writer: $15/mo`, `editor: $5/mo`, `quality: $3/mo`, `specialist: $5/mo`, `orchestrator: $2/mo` (placeholder values — user adjusts). Configure heartbeat endpoint (poll every 5 minutes). Document in `runbooks/control-plane-setup.md`.
- T11.2 — Implement `pipeline/control/paperclip_client.py`. PaperclipClient: wraps Paperclip REST API. `check_budget(agent_role: str) → bool`: GET budget endpoint; return True if remaining > 0. `record_cost(agent_role: str, cost_usd: float, tokens_used: int)`: POST cost entry. `request_approval(gate_name: str, context: dict) → bool`: POST approval request; poll for response with timeout (default 3600s — human has 1 hour to approve before pipeline times out). `heartbeat() → bool`: GET heartbeat endpoint; return True if healthy. Reads PAPERCLIP_API_URL and PAPERCLIP_API_KEY from `.env`.
- T11.3 — Integrate PaperclipClient into orchestrator: (1) `--init-book`: call `paperclip_client.request_approval("spec_sign_off", spec_summary)` before running BookStructurePlanner. (2) `--book-publish`: call `paperclip_client.request_approval("manuscript_sign_off", verification_report)` before assembling output bundle. (3) Every `--job` run: call `check_budget(agent_role)` before invoking each agent; if False → halt with "Budget exceeded for {agent_role}" message. (4) JobRunner: after each scene, call `record_cost()` from cost_log.jsonl last entry.
- T11.4 — Configure WUPHF workspace (already set up from Phase 1 T1.11). Create workspace structure: `series-bible` wiki (git-backed markdown at `.wuphf/{series_id}/wiki/`), `pipeline` channel (one room per book: `book-{n}`), `drafts` channel (agent draft dumps), activity stream (all events from all agents). Document in `runbooks/control-plane-setup.md`.
- T11.5 — Implement `pipeline/control/wuphf_client.py`. WUPHFClient: wraps WUPHF API. `post_to_channel(channel: str, room: str | None, message: str, metadata: dict)`: POST message to channel (with optional room). `update_wiki(page: str, content: str, author: str = "pipeline")`: commit wiki page via WUPHF git-backed wiki API. `read_wiki(page: str) → str`: GET wiki page content. `get_activity_stream(since: datetime) → list[ActivityEvent]`: GET activity stream filtered by timestamp. Reads WUPHF_API_URL and WUPHF_API_KEY from `.env`.
- T11.6 — Integrate WUPHFClient with BibleSteward: in `commit_delta()`, after successful atomic write, call `wuphf_client.update_wiki(f"characters/{entity_id}", entity_markdown)` for all committed entities. Character cards, world facts, and voice profile sections are auto-synced on every bible commit.
- T11.7 — Integrate WUPHFClient with pipeline events: in BaseAgent `run()` logging, also call `wuphf_client.post_to_channel("pipeline", f"book-{book_id}", f"{agent_id} completed {scene_id}: {routing_decision}")`. Activity stream becomes the audit log.
- T11.8 — Implement `pipeline/control/roma_client.py`. ROMAClient: wraps ROMA API (sentient-agi/ROMA). `decompose(series_spec: dict) → DecomposedPlan`: call ROMA Atomizer → Planner → Executor → Aggregator → Verifier pipeline. Returns DecomposedPlan with book_plans list (each: act_plan list, chapter_plan list, scene_plan list). `verify(plan: DecomposedPlan) → VerificationResult`. Note: ROMA drives the planning phase; LangGraph manages per-scene execution. They are complementary, not competing.
- T11.9 — Add `--init-series <series_spec_path>` command to orchestrator: (1) Call `--validate-spec`. (2) Call `paperclip_client.request_approval("series_sign_off", ...)`. (3) Call `roma_client.decompose(series_spec)`. (4) Write book plans as scene inventories for each book. (5) Post plan summary to WUPHF `pipeline` channel.
- T11.10 — Update `.env.example` with PAPERCLIP_API_URL, PAPERCLIP_API_KEY, WUPHF_API_URL, WUPHF_API_KEY placeholders. Document in `runbooks/control-plane-setup.md`.
- T11.11 — Write integration test `tests/integration/test_control_collaboration.py`: (1) ROMA decomposes fixture series spec into a book plan (mock ROMA API or use test mode). (2) Paperclip records a fixture cost entry (mock API or local test instance). (3) WUPHF wiki receives a fixture character card update (mock or local test instance). Verify each client method is called with correct arguments.
- T11.12 — Commit: `feat(control): Paperclip budget enforcement, WUPHF wiki sync, ROMA series decomposition (task-011)`.

## Key decisions that affect this task

- **No human gates in inner loop (DEC-004):** Paperclip approval gates only wrap `--init-book` (spec sign-off) and `--book-publish` (manuscript sign-off). The `--job` execution loop is fully autonomous. Budget enforcement halts the pipeline; approval gates pause it pending human action.
- **ROMA for planning, LangGraph for execution (decisions.md 2026-05-15):** ROMA's Atomizer/Planner/Executor/Aggregator/Verifier drives the series → scene decomposition. LangGraph manages the per-scene state machine. These are complementary layers.
- **WUPHF wiki as series-bible source of truth:** The `series-bible` wiki is git-backed. BibleSteward commits update it. `--validate-spec` can read series spec from wiki. This creates a single source of truth accessible by the human author.
- **Secrets discipline:** PAPERCLIP_API_KEY and WUPHF_API_KEY are never written to committed files. `.env` is gitignored. `.env.example` has placeholders.
- **Local dev only for V1:** Paperclip and WUPHF run locally (from Phase 1 setup). No hosted services.

## Suggested approach

1. Implement PaperclipClient first — test with the locally running Paperclip instance.
2. Integrate PaperclipClient into orchestrator (approval gates + budget checks).
3. Implement WUPHFClient — test wiki update with locally running WUPHF.
4. Integrate WUPHFClient with BibleSteward and BaseAgent logging.
5. Implement ROMAClient — may require ROMA running locally or a test mode.
6. Add `--init-series` command.
7. Write integration test with mocked API clients.
8. Commit.

## Decisions to log in DECISIONS.md

- Approval gate timeout (1 hour default — log chosen value).
- ROMA test mode vs full local instance (document which is used in integration test).
- WUPHF activity stream as audit log (vs separate audit log file — recommend: WUPHF for now; add file-based fallback if WUPHF is unavailable).
- Budget enforcement: halt vs pause (halt chosen — cleaner; pause requires state management).

## Notes

- Paperclip (`paperclipai/paperclip`), WUPHF (`nex-crm/wuphf`), ROMA (`sentient-agi/ROMA`) are confirmed real open-source tools. Read their READMEs before implementing the client wrappers.
- The API shapes of these tools are not fully known from the bundle docs. Read actual API docs / source for each before authoring the client classes.
- Mock clients in integration tests to avoid requiring all three services for CI. The mocks should verify correct call signatures.
- PaperclipClient's `request_approval()` is a long-polling call. In unit tests, mock it to return True immediately.

## Out of scope

- EvoSkill (Phase 12)
- Author Dashboard (Phase 13)
- Cloud hosting of Paperclip/WUPHF (deferred — local dev only for V1)
