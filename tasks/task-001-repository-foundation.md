# Task 001 — Repository Foundation

```
status: pending
started:
completed:
phase: 1
estimated_hours: 4-6
depends_on:
```

## Goal

Working repo skeleton with conventions, tooling, test harness, control-plane stubs (Paperclip + WUPHF), and `model_router.json` defaulting to `test` tier. Every subsequent phase depends on this foundation being solid.

## Phase reference

IMPLEMENTATION_PLAN.md — Phase 1 (Repository Foundation)

## Dependencies

None — this is the first task.

## Acceptance criteria

- [ ] `pyproject.toml` declares all V1 dependencies (anthropic, openai, instructor, pydantic, jsonschema, datamodel-code-generator, pyyaml, pytest, pytest-cov, mypy, ruff, pre-commit, deepeval, langgraph, mem0ai, scikit-learn, scipy, sentence-transformers, numpy)
- [ ] Directory tree matches IMPLEMENTATION_PLAN.md §Phase 1 layout; empty dirs tracked with `.gitkeep`
- [ ] `Makefile` targets: `lint`, `test`, `validate-schemas`, `run-pipeline`, `dashboard`, `format`, `install-dev`
- [ ] `mypy --strict` and `ruff check/format` pass on skeleton
- [ ] Pre-commit hooks installed and fire on commit: ruff, mypy, schema-validator stub
- [ ] `pytest` runs with coverage; smoke test stub `tests/unit/test_smoke.py::test_smoke` passes
- [ ] `.env.example` documents ANTHROPIC_API_KEY, OPENAI_API_KEY, OLLAMA_HOST
- [ ] `model_router.json` at repo root defaults `model_tier = "test"` (Haiku 4.5 / gpt-4.1-mini / Ollama phi3.5)
- [ ] `DECISIONS.md` at repo root (DEC-NNN format) pre-populated with all 11 standing decisions from IMPLEMENTATION_PLAN.md §Pre-implementation standing decisions
- [ ] Paperclip (Docker) running locally; first "series" company created; heartbeat green
- [ ] WUPHF (binary) running locally; workspace with `series-bible` wiki and `pipeline` channel accessible
- [ ] `ollama pull phi3.5` complete; `ollama run phi3.5 "ping"` responds
- [ ] `make lint && make test` passes on clean checkout

## Subtasks

- T1.1 — Author `pyproject.toml` with PEP 621 metadata and all V1 dependencies. Use `uv pip install` to install into `.venv`.
- T1.2 — Create directory tree: `pipeline/`, `pipeline/core/`, `pipeline/ledgers/`, `pipeline/profiles/`, `pipeline/continuity/`, `pipeline/control/`, `pipeline/evoskill/`, `api/`, `dashboard/`, `schemas/universal/`, `schemas/ledgers/`, `schemas/profiles/`, `profiles/author/`, `profiles/genre/`, `profiles/audience/`, `profiles/sensitivity/`, `profiles/goal/`, `tests/unit/`, `tests/integration/`, `tests/eval/`, `tests/fixtures/`, `scripts/`, `data/`, `runbooks/`. Add `__init__.py` to all `pipeline/` sub-packages; `.gitkeep` to empty leaf dirs.
- T1.3 — Author `Makefile` with targets: `lint` (ruff + mypy --strict), `test` (pytest --cov), `validate-schemas` (calls `scripts/validate_schemas.py` stub), `run-pipeline` (calls `pipeline/orchestrator.py --help`), `dashboard` (starts FastAPI + npm dev server), `format` (ruff format), `install-dev` (uv pip install -e ".[dev]").
- T1.4 — Configure `ruff.toml` (line-length 100, select all relevant rules) and `mypy.ini` (strict mode, plugins = pydantic.mypy).
- T1.5 — Configure `.pre-commit-config.yaml`: ruff check, ruff format, mypy, schema-validator stub. Run `pre-commit install`.
- T1.6 — Write smoke test `tests/unit/test_smoke.py`: single `test_smoke` that asserts True. Verify `make test` passes.
- T1.7 — Write `.env.example` with ANTHROPIC_API_KEY, OPENAI_API_KEY, OLLAMA_HOST placeholder values and comments.
- T1.8 — Write `model_router.json`: `{"model_tier": "test", "test": {"anthropic": "claude-haiku-4-5", "openai": "gpt-4.1-mini", "local": "phi3.5"}, "production": {"anthropic": "claude-sonnet-4-6", "openai": "gpt-4.1", "local": "phi3.5"}}`.
- T1.9 — Write `DECISIONS.md` at repo root. Pre-populate DEC-001 through DEC-011 matching the 11 standing decisions in IMPLEMENTATION_PLAN.md §Pre-implementation standing decisions. Use the DEC-NNN YAML block format from the Starter CLAUDE.md.
- T1.10 — Install dependencies: `uv pip install anthropic openai instructor pydantic jsonschema datamodel-code-generator pyyaml pytest pytest-cov mypy ruff pre-commit deepeval langgraph mem0ai scikit-learn scipy sentence-transformers numpy`. Log any version pins needed.
- T1.11 — Stand up Paperclip via Docker. Create first "series" company. Verify heartbeat endpoint returns green. Stand up WUPHF binary. Create workspace; add `series-bible` wiki (git-backed) and `pipeline` channel. Document startup commands in `runbooks/control-plane-setup.md`.
- T1.12 — Pull Ollama test-tier model: `ollama pull phi3.5`. Verify `ollama run phi3.5 "ping"` responds.
- T1.13 — Write `scripts/validate_schemas.py` stub (no-op that prints "No schemas yet" and exits 0). `make validate-schemas` calls it.
- T1.14 — Make initial commit: `chore: initial repository scaffolding (task-001)`.

## Key decisions that affect this task

- **Model tiering (DEC-009):** `model_router.json` must default to `test` tier. Do not hardcode any model names in Python — everything reads from this file via ModelRouter (Phase 6).
- **Heavier-weight from start (DEC-008):** Even the skeleton must be `mypy --strict` clean. Do not defer strict typing.
- **Local dev only for V1:** No cloud services beyond Anthropic API. Paperclip and WUPHF run locally.
- **Secrets discipline:** No API key written into any file. `.env` is gitignored. `.env.example` has placeholders only.

## Suggested approach

1. Read IMPLEMENTATION_PLAN.md Phase 1 tasks list end to end before writing any file.
2. Create pyproject.toml and Makefile first — they define the constraint surface.
3. Create directories + __init__.py files. Keep `tree` output to verify against layout.
4. Install dependencies into `.venv` via `uv pip install`.
5. Configure mypy + ruff; verify they pass on empty skeleton.
6. Add pre-commit config and run `pre-commit install`.
7. Write smoke test; run `make test`.
8. Write DECISIONS.md with all 11 standing decisions.
9. Set up Paperclip + WUPHF + Ollama; document in runbook.
10. Commit.

## Decisions to log in DECISIONS.md

- Build tooling choice (pyproject.toml + uv).
- Lint/format choice (ruff for both).
- Test runner choice (pytest + coverage).
- Model router format (JSON config file vs code constants).
- Paperclip/WUPHF local setup approach.

## Out of scope

- Any pipeline implementation code
- JSON schemas (Phase 2)
- Profile data (Phase 5)
- CI/CD
- Docker for the pipeline itself (Paperclip uses Docker; pipeline does not yet)
