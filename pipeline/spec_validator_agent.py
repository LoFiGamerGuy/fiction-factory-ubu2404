"""SpecValidatorAgent — validates series/book spec YAML files.

Checks:
  1. YAML parseable
  2. Required top-level keys present
  3. No sentinel strings ("REQUIRED — fill in")
  4. JSON Schema validation (when schema is available)

Thin wrapper over pipeline.spec_loader.SeriesSpecLoader.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.spec_loader import SentinelStringError, SeriesSpecLoader, SpecLoadError

logger = logging.getLogger(__name__)

_REQUIRED_SERIES_KEYS = frozenset({"series_id", "genre_config"})


@dataclass
class SpecValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


class SpecValidatorAgent:
    """Validates a spec YAML file; returns SpecValidationResult with error list."""

    def __init__(self, schema_path: Path | None = None) -> None:
        self._loader = SeriesSpecLoader(schema_path=schema_path)

    def validate(self, spec_path: Path) -> SpecValidationResult:
        """Run all checks against spec_path. Never raises — errors go in result."""
        errors: list[str] = []

        try:
            data = self._loader.load(spec_path)
        except SentinelStringError as exc:
            errors.append(f"Sentinel string: {exc}")
            return SpecValidationResult(valid=False, errors=errors)
        except SpecLoadError as exc:
            errors.append(f"Load error: {exc}")
            return SpecValidationResult(valid=False, errors=errors)
        except Exception as exc:
            errors.append(f"Unexpected error: {exc}")
            return SpecValidationResult(valid=False, errors=errors)

        # Required top-level keys
        for key in _REQUIRED_SERIES_KEYS:
            if key not in data:
                errors.append(f"Missing required key: '{key}'")

        if errors:
            return SpecValidationResult(valid=False, errors=errors)

        logger.info("SpecValidatorAgent: %s is valid", spec_path)
        return SpecValidationResult(valid=True)
