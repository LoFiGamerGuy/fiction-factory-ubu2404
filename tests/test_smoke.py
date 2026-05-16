"""
Phase 1 smoke tests — verify repo skeleton is correct.
Phase 7 adds the full end-to-end scene smoke test (T7.9).
"""

import json
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent


def test_model_router_exists() -> None:
    assert (WORKSPACE_ROOT / "model_router.json").exists()


def test_model_router_default_tier_is_test() -> None:
    config = json.loads((WORKSPACE_ROOT / "model_router.json").read_text())
    assert config["model_tier"] == "test", "Default tier must be 'test' — DEC-000-9"


def test_env_example_exists() -> None:
    assert (WORKSPACE_ROOT / ".env.example").exists()


def test_schemas_directory_populated() -> None:
    files = list((WORKSPACE_ROOT / "schemas").rglob("*.schema.json"))
    assert len(files) > 0


def test_pipeline_package_importable() -> None:
    assert (WORKSPACE_ROOT / "pipeline" / "__init__.py").exists()


def test_all_task_files_present() -> None:
    tasks_dir = WORKSPACE_ROOT / "tasks"
    for i in range(1, 16):
        prefix = f"task-{str(i).zfill(3)}"
        matches = list(tasks_dir.glob(f"{prefix}*.md"))
        assert matches, f"Missing task file for {prefix}"
