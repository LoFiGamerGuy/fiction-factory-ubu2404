"""pipeline.spec_loader — Series/book spec loader with sentinel string rejection.

Validates YAML against JSON Schema and rejects any field with value
"REQUIRED — fill in" (MBSE B4/B5 fix).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

_SENTINEL = "REQUIRED — fill in"


class SentinelStringError(ValueError):
    """Raised when a spec contains an unfilled sentinel string."""


class SpecLoadError(ValueError):
    """Raised when a spec fails to load or fails schema validation."""


def _walk_sentinel(obj: Any, path: str = "") -> None:
    """Recursively walk a parsed YAML object; raise on sentinel strings."""
    if isinstance(obj, str) and obj == _SENTINEL:
        raise SentinelStringError(f"Spec contains unfilled sentinel at {path!r}: {_SENTINEL!r}")
    if isinstance(obj, dict):
        for k, v in obj.items():
            _walk_sentinel(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _walk_sentinel(item, f"{path}[{i}]")


class SeriesSpecLoader:
    """Loads and validates series/book spec YAML files.

    Schema validation is performed when a schema path is provided.
    Sentinel string check is always performed.
    """

    def __init__(
        self,
        workspace_root: Path = Path("."),
        schema_path: Path | None = None,
    ) -> None:
        self._root = workspace_root
        self._schema: dict[str, Any] | None = None
        if schema_path and schema_path.exists():
            self._schema = json.loads(schema_path.read_text(encoding="utf-8"))

    def load(self, spec_path: Path) -> dict[str, Any]:
        """Load a YAML spec, validate, and return the parsed dict."""
        if not spec_path.exists():
            raise SpecLoadError(f"Spec file not found: {spec_path}")

        try:
            raw: Any = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise SpecLoadError(f"YAML parse error in {spec_path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise SpecLoadError(f"Spec must be a YAML mapping: {spec_path}")

        # Sentinel check — always applied
        _walk_sentinel(raw)

        # Schema validation — applied when schema is available
        if self._schema is not None:
            try:
                jsonschema.validate(instance=raw, schema=self._schema)
            except jsonschema.ValidationError as exc:
                raise SpecLoadError(
                    f"Spec {spec_path} failed schema validation: {exc.message}"
                ) from exc

        return raw

    def load_series_spec(self, series_id: str) -> dict[str, Any]:
        return self.load(self._root / "data" / "series" / series_id / "spec.yaml")

    def load_book_spec(self, series_id: str, book_id: str) -> dict[str, Any]:
        return self.load(self._root / "data" / "series" / series_id / book_id / "spec.yaml")
