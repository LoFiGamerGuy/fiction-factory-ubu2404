"""Shared pytest fixtures."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.profiles.project_spec import (
    ProjectSpec,
    ResolvedAudienceExpectations,
    ResolvedGenreConfig,
    ResolvedGoalWeights,
    ResolvedSensitivityThresholds,
    ResolvedVoiceAxes,
)

WORKSPACE_ROOT = Path(__file__).parent.parent


@pytest.fixture
def workspace_root() -> Path:
    return WORKSPACE_ROOT


@pytest.fixture
def schemas_dir() -> Path:
    return WORKSPACE_ROOT / "schemas"


@pytest.fixture
def mock_project_spec() -> ProjectSpec:
    """Minimal ProjectSpec for testing."""
    return ProjectSpec(
        series_id="test-series",
        book_id="test-book-01",
        voice_axes=ResolvedVoiceAxes(),
        genre_config=ResolvedGenreConfig(),
        audience_expectations=ResolvedAudienceExpectations(),
        goal_weights=ResolvedGoalWeights(),
        sensitivity_thresholds=ResolvedSensitivityThresholds(),
    )


@pytest.fixture
def mock_model_router() -> MagicMock:
    """Mock ModelRouter for testing."""
    router = MagicMock()
    router.call.return_value = MagicMock(edited_text="Edited text placeholder")
    return router
