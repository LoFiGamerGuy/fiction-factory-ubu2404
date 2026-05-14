# Systems Architecture — Fiction-Factory Bundle Review & Synthesis

Workspace for reviewing and synthesizing three architecture bundles for an
autonomous AI fiction-novel-writing pipeline.

## Three-bundle situation

Three planning bundles live as zip archives in the workspace root:

- `Using MBSE to Deconstruct and Spec a Fiction Novel.zip` — most mature; 166 files including Python orchestrator/agents, TSX UI components, multiple craft reviews, SME personas, closure memos.
- `autonomous-book-pipeline-starter.zip` — clean starter kit: CLAUDE.md, IMPLEMENTATION_PLAN, ontology v3, schemas, runbooks, task backlog, v5 architecture diagram.
- `bunko_files.zip` — BUNKO-ARCH v0.1→v0.2 + voice profile schema; genre/bunko fiction scope.

**Authorship:** all three are the user's own work. Synthesize is the default
disposition unless review reveals a clear winner. Bundle stakeholder voices
(Manus, Dr. Smith, Romance/Literary/Thriller SMEs) are historical — the user
owns the final call.

## Plan of record

The governing plan for the review-and-synthesis work is:
**`/home/gosne/.claude/plans/in-this-folder-you-deep-toast.md`**

That plan is the **baseline** as of 2026-05-14 (Phase 0 complete). All deviations
require an explicit baseline change request appended to the plan file — see
"Change control" in that document.

### Approval gates (when execution pauses for user)

1. End of Phase 0 — Pass 1 tooling install + extraction + memory seed
2. §2.1.6 — synthesis-shape early scoping question
3. §2.4 — synthesis-shape final binding question
4. End of Phase 3 (Pass 2) — `.workspace/TOOLING_DECISIONS.md` adopt/defer/replace approval
5. End of Phase 4 — `IMPLEMENTATION_PLAN.md` approval

## Glossary

Canonical terminology lives in
`/home/gosne/.claude/projects/-home-gosne-src-workspace-Systems-Architecture/memory/glossary.md`
(seeded in Phase 0, populated during Phase 2.1 triage).

Glossary collision resolution rule: domain-specificity → most-recent bundle → user adjudication. See plan §"Glossary collision resolution rule".

## Workspace layout

- **Workspace root** — the three original zips (authoritative baseline, committed in git).
- **`.workspace/`** — scratch tree; gitignored; regenerable from the zips. Contains:
  - `.workspace/bundles/{mbse,starter,bunko}/` — extracted bundles.
  - `.workspace/bundles/mbse/_nested/` — extracted MBSE nested zips (9 of them).
  - `.workspace/TIMELINE.md`, `.workspace/COMPARISON.md`, `.workspace/TOOLING_DECISIONS.md` — produced during review.
- **`memory/` (Claude memory dir)** — `project_three_bundles.md`, `glossary.md`, `stakeholders.md`, `decisions.md`.

## Runtime constraints

- Python 3.12 (system); `uv` 0.11.14 (installed Phase 0 via [BCR uv-pulled-forward]).
- **Local dev only for v1** — no cloud, no packaging, no hosted services unless explicitly opted in during Phase 3 Axis B review.
- Paid services cited in bundles (Together AI, Apify, Bright Data, Composio, etc.) are deferred by default.
- Cloud GPU (AWS GPU, Sentient-Enclaves) deferred.
- The Anthropic API is in-bounds (existing user setup).

## Secrets

- `ANTHROPIC_API_KEY` sourced from existing environment / `~/.claude/.credentials.json`.
- Any new secret required by an adopted Axis-B tool triggers stop-and-ask before adoption.
- No secret is written into `.workspace/`, `memory/`, or any committed file.
- `.env` is gitignored; provide `.env.example` with placeholders when one is needed.

## Tooling installed (Phase 0 / Pass 1)

**Plugins:** `claude-md-management`, `claude-code-setup`, `session-report` (all from `claude-plugins-official`).
**MCP servers:** `serena` (semantic code nav), `context7` (SDK doc lookup).
**Toolchain:** `pipx`, `uv` 0.11.14.

Pass 2 tooling (`pyright-lsp`, `mcp-server-dev`, `hookify`, `ralph-loop`, `atomic-agents`, plus bundle-cited Axis-B tools) is reviewed after Phase 2 review decisions, per the plan's Phase 3.

## Change control

Once Phase 0 commits land, the plan above is the baseline.

- No deviation from scope/approach/tooling/outputs without an explicit baseline change request appended to the plan file.
- Any tool, library, or service not listed in the plan being about to be installed/invoked → change request.
- Any memory file schema change → change request.
- Minor housekeeping (typos, path corrections, additional verifications that don't change outcomes) doesn't require a change request but is noted in `memory/decisions.md`.

See the plan file's "Change control" section for the full process.
