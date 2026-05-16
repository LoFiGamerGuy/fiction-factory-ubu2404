"""Shared pytest fixtures."""

from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).parent.parent


@pytest.fixture
def workspace_root() -> Path:
    return WORKSPACE_ROOT


@pytest.fixture
def schemas_dir() -> Path:
    return WORKSPACE_ROOT / "schemas"
