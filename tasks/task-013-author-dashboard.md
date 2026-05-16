# Task 013 — Author Dashboard

```
status: pending
started:
completed:
phase: 13
estimated_hours: 12-18
depends_on: task-012
```

## Goal

Live monitoring + historical browse for the author. FastAPI backend with SSE for live updates. React frontend extending the manus-agnostic TSX shell with Live View and Historical View components. Agent-information delivery is the first priority — every component must surface what the pipeline is doing, not just aesthetic metrics. `make dashboard` starts both services.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 13 (Author Dashboard)

## Dependencies

- task-003 (LedgerManager + all 10 ledger classes — all dashboard data comes from ledgers)
- task-012 (EvoSkillClient — SkillLibrary component queries accumulated skills)
- task-011 (PaperclipClient — cost vs budget displayed in RunMonitor)
- task-007 (scene state machine — SSE events pushed on each state transition)

## Acceptance criteria

- [ ] `api/main.py` — FastAPI app with all 7 required endpoints
- [ ] `GET /runs/{run_id}/status` — current pipeline state (active scene, current agent, routing decisions)
- [ ] `GET /runs/{run_id}/stream` — SSE endpoint for live updates; events pushed on each agent completion and routing decision
- [ ] `GET /books/{book_id}/ledgers` — all 10 ledger states for a completed/active book
- [ ] `GET /books/{book_id}/metrics/history` — chapter-by-chapter metric trajectory (interiority%, sensory density, heat curve, etc.)
- [ ] `GET /series/{series_id}/promises` — Series Promise Ledger state
- [ ] `GET /series/{series_id}/evoskill` — accumulated skill library for series
- [ ] `GET /books/{book_id}/quality_gates` — scene-by-scene quality gate decision history
- [ ] React shell extended from manus-agnostic TSX components
- [ ] `RunMonitor.tsx` — current run: agent, scene, routing decision, cost vs budget (Paperclip)
- [ ] `LedgerDashboard.tsx` — all 10 ledger states with targets and budget remaining; visual dials/bars
- [ ] `QualityFeed.tsx` — live stream of quality gate decisions via SSE
- [ ] `MetricTrajectory.tsx` — line chart: metrics chapter-by-chapter (configurable: which metrics to plot)
- [ ] `PromiseLedger.tsx` — all promises: open/resolved/overdue; timeline view
- [ ] `IntimacyTimeline.tsx` — character pair intimacy escalation map
- [ ] `SeriesTimeline.tsx` — cross-book series promise and arc tracker
- [ ] `VoiceCalibration.tsx` — voice profile calibration history across books
- [ ] `SkillLibrary.tsx` — EvoSkill accumulated patterns per series
- [ ] `make dashboard` starts FastAPI backend + React dev server; both accessible at localhost
- [ ] Live view test: SSE events received during a smoke-test run (agent completion events arrive at QualityFeed)
- [ ] Historical view test: all 10 ledger states rendered correctly for a fixture completed book
- [ ] `make test` passes (backend unit tests; frontend component tests optional for V1)

## Subtasks

- T13.1 — Implement `api/main.py`. FastAPI app. Import LedgerManager from pipeline. Each endpoint queries the appropriate ledger(s):
  - `GET /runs/{run_id}/status`: read `data/{run_id}/run_state.json` (written by job_runner on each state transition). Returns `{active_scene, current_agent, routing_decision, revise_count, cost_vs_budget}`.
  - `GET /runs/{run_id}/stream`: SSE endpoint using `fastapi.responses.StreamingResponse` with `text/event-stream`. job_runner writes events to a Redis pub-sub or a local SSE event queue; API reads and streams. For V1: use a local async queue (no Redis dependency). Events: `{event: "agent_complete", data: {agent_id, scene_id, duration_ms, routing_decision}}`.
  - `GET /books/{book_id}/ledgers`: call `LedgerManager.get_dashboard_summary(book_id, "current")`. Return AuthorDashboard as JSON.
  - `GET /books/{book_id}/metrics/history`: query BookMetricsLedger for all events for book_id; group by chapter_id; return chapter → metric map.
  - `GET /series/{series_id}/promises`: query SeriesPromiseLedger for all events for series_id; return grouped by promise_id.
  - `GET /series/{series_id}/evoskill`: read `data/{series_id}/skills/` directory; return list of skill summaries.
  - `GET /books/{book_id}/quality_gates`: read all scene routing decisions from `data/{book_id}/quality_gate_history.jsonl`; return list.
- T13.2 — Update `Makefile` `dashboard` target: `make dashboard` runs `uvicorn api.main:app --reload --port 8000 & cd dashboard && npm run dev`. Document startup in `runbooks/dashboard-setup.md`.
- T13.3 — Set up React project in `dashboard/`. If manus-agnostic TSX shell exists in `.workspace/manus-agnostic/`: copy relevant TSX/TS files as starting point (App.tsx, AdminView, SeriesView, BooksView, ChaptersView, ActsView, etc.). Update package.json if needed. Configure proxy: `dashboard/vite.config.ts` proxies `/api` to `http://localhost:8000`.
- T13.4 — Implement `dashboard/src/components/live/RunMonitor.tsx`. Fetches `GET /runs/{run_id}/status` on 5-second poll. Displays: current agent (badge), current scene (chapter/scene ids), routing decision (colored badge: GO=green, REVISE=yellow, RE-PLAN=orange, FORCE-RESOLVE=red), Paperclip cost vs budget (progress bar per agent role), revise count.
- T13.5 — Implement `dashboard/src/components/live/LedgerDashboard.tsx`. Fetches `GET /books/{book_id}/ledgers`. Displays all 10 ledger states: BookMetrics (dial charts for interiority%, dialogue_ratio, heat_curve_position, ai_tell_count vs targets), CharacterArc (table: character → arc_position + wound_state), IntimacyEscalation (list of pairs with last_act_type and heat_level), ReaderInfoState (facts known/unknown counts), SubplotLedger (open/closed subplot count), TropeCommitment (pending/overdue beats), SeriesPromise (open cross-book promises), SceneRhythm (last 10 scene types as tag sequence), PromiseSummary (open/overdue count).
- T13.6 — Implement `dashboard/src/components/live/QualityFeed.tsx`. Connects to `GET /runs/{run_id}/stream` SSE endpoint. Displays incoming quality gate events as a feed (newest first): agent_id, scene_id, routing_decision, critic scores if present. Routing decisions color-coded.
- T13.7 — Implement `dashboard/src/components/historical/MetricTrajectory.tsx`. Fetches `GET /books/{book_id}/metrics/history`. Renders line chart (recharts or visx) with configurable metrics: which metrics to plot is selectable by the user (checkboxes). X-axis: chapter number. Y-axis: normalized metric value. Overlay targets as dashed lines. Required metrics at minimum: interiority_pct, dialogue_ratio, heat_curve_position, ai_tell_count, sensory_density_per_1k.
- T13.8 — Implement `dashboard/src/components/historical/PromiseLedger.tsx`. Fetches `GET /books/{book_id}/ledgers` (PromiseSummary section). Displays all promises in a table: promise_id, type, opened_at chapter, must_resolve_by chapter, resolution_state (color-coded: open=blue, resolved=green, overdue=red, force_resolved=orange). Optional: timeline visualization (horizontal bars per promise).
- T13.9 — Implement `dashboard/src/components/historical/IntimacyTimeline.tsx`. Fetches IntimacyEscalation ledger data. Displays per-pair escalation as a horizontal timeline: act_type events in sequence, color-coded by heat_level. Useful for checking erotica subtype escalation compliance visually.
- T13.10 — Implement `dashboard/src/components/historical/SeriesTimeline.tsx`. Fetches `GET /series/{series_id}/promises`. Displays cross-book series promises: horizontal bars spanning opened_book to must_resolve_by_book. Color by resolution_status.
- T13.11 — Implement `dashboard/src/components/historical/VoiceCalibration.tsx`. Fetches voice profile calibration history (from author_profile.yaml `calibration_history` field + any calibration run records). Displays: axis-level drift from target across books (table or small multiples).
- T13.12 — Implement `dashboard/src/components/historical/SkillLibrary.tsx`. Fetches `GET /series/{series_id}/evoskill`. Displays accumulated EvoSkill guidelines as cards: condition, recommendation, when_added. Filter by failure_mode type.
- T13.13 — Write backend tests `tests/unit/api/test_dashboard_api.py`: each endpoint tested with fixture ledger data (mock LedgerManager). Verify response schema for each endpoint.
- T13.14 — Write SSE test `tests/integration/test_sse_live_view.py`: start FastAPI test client; send a mock agent_complete event via the queue; verify SSE stream emits correctly formatted event.
- T13.15 — Commit: `feat(dashboard): FastAPI backend + React Live View + Historical Browse (task-013)`.

## Key decisions that affect this task

- **Agent-information delivery first priority (decisions.md 2026-05-15):** Every component surfaces what the pipeline is doing (agent, routing, ledger state) — not just visual aesthetics. RunMonitor and LedgerDashboard are the most important components.
- **FastAPI + SSE (no WebSockets for V1):** SSE is simpler and sufficient for the live-update pattern. No Redis dependency for V1 — use local async queue.
- **Extending manus-agnostic TSX shell:** Read the ~21 manus-agnostic TSX/TS files in `.workspace/manus-agnostic/` before starting. Understand the existing component structure and routing before adding new components.
- **All ledger data from LedgerManager:** The API never queries SQLite directly — it goes through LedgerManager.get_dashboard_summary(). This is the same interface used by the pipeline.
- **`make dashboard` target:** Both FastAPI backend and React dev server must start with a single command. No manual multi-step startup.

## Suggested approach

1. Read all ~21 TSX/TS files in `.workspace/manus-agnostic/` to understand the existing shell structure.
2. Implement FastAPI backend first — all 7 endpoints with fixture data.
3. Test all endpoints with `pytest tests/unit/api/` before writing any React.
4. Set up React project; configure proxy to FastAPI.
5. Implement Live View components (RunMonitor, LedgerDashboard, QualityFeed) — these are highest value.
6. Implement Historical View components in priority order: MetricTrajectory, PromiseLedger, IntimacyTimeline, SeriesTimeline, VoiceCalibration, SkillLibrary.
7. Update Makefile dashboard target; verify `make dashboard` starts both services.
8. Write SSE integration test.
9. Commit.

## Decisions to log in DECISIONS.md

- SSE vs WebSockets (SSE chosen for V1 simplicity; log this tradeoff).
- Local async queue vs Redis for SSE events (local for V1 — log the dependency-free choice).
- Chart library choice (recharts vs visx vs chart.js — log rationale).
- MetricTrajectory configurable metrics UX (checkboxes vs dropdown).

## Notes

- Manus-agnostic TSX files in `.workspace/manus-agnostic/`: PipelineStatus, App, Admin, Series, SeriesBible, ARC, ActsView, BooksView, ChaptersView, etc. These are the starting point for the React shell — do not start from scratch.
- MBSE `Book Organizer: Graphical Interface Specification.md` has additional UI requirements. Read it before implementing the historical view components.
- The IntimacyTimeline is directly useful for erotica/romance production monitoring: the author can see escalation compliance at a glance.
- For V1, frontend component tests (Jest/Vitest) are optional — focus on backend tests and manual verification of the UI.

## Out of scope

- Mobile / responsive design (desktop first for V1)
- User authentication (single-user local dev)
- Real-time collaboration (single user)
- Export to PDF or print layout
- Voice Discriminator / fine-tuned scoring (V2 roadmap)
