PYTHON := .venv/bin/python
UV     := uv
DASHBOARD_DATA_ROOT ?= data
DASHBOARD_RUN_ID ?= default
DASHBOARD_BOOK_ID ?= default
DASHBOARD_SERIES_ID ?= default
DASHBOARD_CHARACTER_IDS ?= sarah,miles

.PHONY: install lint test validate-schemas eval phase14-acceptance book-acceptance run-pipeline dashboard hooks clean

## First-time setup: create venv, install all deps, install hooks
install:
	$(UV) venv .venv
	$(UV) pip install -e ".[dev]"
	$(UV) pip install booknlp || echo "[warn] booknlp install failed — install manually if needed"
	$(UV) pip install roma-dspy || echo "[warn] roma-dspy install failed — clone sentient-agi/ROMA if needed"
	.venv/bin/python -m spacy download en_core_web_sm
	.venv/bin/pre-commit install
	@echo "Install complete. Copy .env.example to .env and fill in keys."

## Lint + type-check
lint:
	.venv/bin/ruff check pipeline/ agents/ api/ scripts/ tests/
	.venv/bin/ruff format --check pipeline/ agents/ api/ scripts/ tests/
	.venv/bin/mypy pipeline/ agents/ api/ --strict --ignore-missing-imports

## Run test suite
test:
	.venv/bin/pytest tests/ -v --cov=pipeline --cov=agents

## Validate all JSON Schema files
validate-schemas:
	$(PYTHON) scripts/validate_schemas.py

## Run Phase 14 eval metrics (pass EVAL_ARGS="--scene path/to/scene.md")
eval:
	$(PYTHON) scripts/run_eval.py $(EVAL_ARGS)

## Run Phase 14 three-scene acceptance (pass PHASE14_ARGS="--model-tier test")
phase14-acceptance:
	$(PYTHON) scripts/run_phase14_acceptance.py $(PHASE14_ARGS)

## Run short-book acceptance (pass BOOK_ACCEPTANCE_ARGS="--model-tier test")
book-acceptance:
	$(PYTHON) scripts/run_book_acceptance.py $(BOOK_ACCEPTANCE_ARGS)

## Run the pipeline orchestrator CLI (pass ARGS="--help" etc.)
run-pipeline:
	$(PYTHON) -m pipeline.orchestrator $(ARGS)

## Start Author Dashboard (Phase 13): FastAPI on :8000 + React dev server
dashboard:
	@echo "Starting FastAPI backend on http://localhost:8000 ..."
	FF_DASHBOARD_DATA_ROOT="$(DASHBOARD_DATA_ROOT)" $(PYTHON) -m uvicorn api.main:app --reload --port 8000 &
	@echo "Starting React frontend ..."
	cd dashboard && VITE_DEFAULT_RUN_ID="$(DASHBOARD_RUN_ID)" VITE_DEFAULT_BOOK_ID="$(DASHBOARD_BOOK_ID)" VITE_DEFAULT_SERIES_ID="$(DASHBOARD_SERIES_ID)" VITE_DEFAULT_CHARACTER_IDS="$(DASHBOARD_CHARACTER_IDS)" npm run dev

## Install pre-commit hooks (already called by `make install`)
hooks:
	.venv/bin/pre-commit install

## Remove generated artefacts
clean:
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -not -path "./.venv/*" -delete 2>/dev/null || true
	rm -rf dist *.egg-info .mypy_cache .pytest_cache .ruff_cache htmlcov
