"""VoiceProfile — typed wrapper over the author_profile YAML schema.

Loads from profiles/author/*.yaml, validates against author_profile.schema.json,
and exposes forbidden_constructions as compiled regex patterns (Bunko schema §2).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import yaml


class VoiceProfile:
    """Structured access to an author's voice profile.

    Wraps the raw author_profile YAML dict and adds:
    - ``forbidden_constructions_compiled``: list of compiled regex patterns
    - Typed property access for enforcement_weights and calibration_history
    """

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        self._forbidden_patterns: list[re.Pattern[str]] = [
            re.compile(p) for p in raw.get("forbidden_constructions", [])
        ]

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    def profile_id(self) -> str:
        return str(self._raw.get("profile_id", ""))

    @property
    def version(self) -> str:
        return str(self._raw.get("version", ""))

    @property
    def display_name(self) -> str:
        return str(self._raw.get("display_name", ""))

    # ── Voice axes ────────────────────────────────────────────────────────────

    @property
    def voice_axes(self) -> dict[str, Any]:
        result: dict[str, Any] = self._raw.get("voice_axes", {})
        return result

    def axis_group(self, group: str) -> dict[str, Any]:
        result: dict[str, Any] = self.voice_axes.get(group, {})
        return result

    # ── Enforcement ───────────────────────────────────────────────────────────

    @property
    def enforcement_weights(self) -> dict[str, float]:
        raw_weights: dict[str, Any] = self._raw.get("enforcement_weights", {})
        return {k: float(v) for k, v in raw_weights.items()}

    @property
    def forbidden_constructions_raw(self) -> list[str]:
        result: list[str] = self._raw.get("forbidden_constructions", [])
        return result

    @property
    def forbidden_constructions_compiled(self) -> list[re.Pattern[str]]:
        return self._forbidden_patterns

    # ── Calibration history ───────────────────────────────────────────────────

    @property
    def calibration_history(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._raw.get("calibration_history", [])
        return result

    # ── Raw access ────────────────────────────────────────────────────────────

    def raw(self) -> dict[str, Any]:
        return self._raw

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def load(
        cls,
        profile_path: Path,
        schema_path: Path | None = None,
    ) -> VoiceProfile:
        """Load an author profile YAML, validate it, and return a VoiceProfile.

        If ``schema_path`` is provided the YAML is validated against that schema.
        If omitted, validation is skipped (useful for lightweight callers).
        """
        if not profile_path.exists():
            raise FileNotFoundError(f"Author profile not found: {profile_path}")

        raw: Any = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Author profile must be a YAML mapping: {profile_path}")

        if schema_path is not None:
            if not schema_path.exists():
                raise FileNotFoundError(f"Author profile schema not found: {schema_path}")
            schema: dict[str, Any] = json.loads(schema_path.read_text())
            try:
                jsonschema.validate(instance=raw, schema=schema)
            except jsonschema.ValidationError as exc:
                raise ValueError(
                    f"Author profile {profile_path.name!r} failed schema validation: {exc.message}"
                ) from exc

        return cls(raw)

    def __repr__(self) -> str:
        return f"<VoiceProfile id={self.profile_id!r} version={self.version!r}>"
