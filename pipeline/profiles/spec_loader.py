"""SpecLoader — loads and validates YAML profile files against JSON schemas.

Pins profile versions at load time. Every call returns a validated dict;
callers (ConflictResolver, ProfileRegistry) use the raw dict for flexibility.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml


class ProfileLoadError(Exception):
    """Raised when a profile cannot be loaded or fails schema validation."""


_SCHEMA_MAP: dict[str, str] = {
    "author": "schemas/profiles/author_profile.schema.json",
    "genre": "schemas/profiles/genre_profile.schema.json",
    "audience": "schemas/profiles/audience_profile.schema.json",
    "sensitivity": "schemas/profiles/sensitivity_profile.schema.json",
    "goal": "schemas/profiles/goal_profile.schema.json",
}

_PROFILES_ROOT = Path("profiles")


class SpecLoader:
    """Loads profile YAML from disk, validates against JSON schema, returns raw dict."""

    def __init__(self, workspace_root: Path = Path(".")) -> None:
        self._root = workspace_root

    def _schema(self, profile_type: str) -> dict[str, Any]:
        rel = _SCHEMA_MAP.get(profile_type)
        if rel is None:
            raise ProfileLoadError(f"Unknown profile type: '{profile_type}'")
        path = self._root / rel
        if not path.exists():
            raise ProfileLoadError(f"Schema file not found: {path}")
        return json.loads(path.read_text())  # type: ignore[no-any-return]

    def load(self, profile_type: str, name: str) -> dict[str, Any]:
        """Load `profiles/{type}/{name}.yaml`, validate, return dict with version pinned."""
        if profile_type not in _SCHEMA_MAP:
            raise ProfileLoadError(f"Unknown profile type: '{profile_type}'")
        yaml_path = self._root / _PROFILES_ROOT / profile_type / f"{name}.yaml"
        if not yaml_path.exists():
            raise ProfileLoadError(f"Profile not found: {yaml_path}")

        raw = yaml.safe_load(yaml_path.read_text())
        if not isinstance(raw, dict):
            raise ProfileLoadError(f"Profile YAML must be a mapping: {yaml_path}")

        schema = self._schema(profile_type)
        try:
            jsonschema.validate(instance=raw, schema=schema)
        except jsonschema.ValidationError as exc:
            raise ProfileLoadError(
                f"Profile '{name}' ({profile_type}) failed schema validation: {exc.message}"
            ) from exc

        raw["_profile_type"] = profile_type
        raw["_loaded_from"] = str(yaml_path)
        return raw

    def get_series_spec_path(self, series_id: str) -> Path:
        return self._root / "data" / "series" / series_id / "spec.yaml"

    def get_book_spec_path(self, series_id: str, book_id: str) -> Path:
        return self._root / "data" / "series" / series_id / book_id / "spec.yaml"
