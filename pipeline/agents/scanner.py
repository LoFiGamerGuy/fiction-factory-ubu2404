"""NoFlyScanner — deterministic regex-based AI-tell scanner.

Loads patterns from the ai_tell_catalog JSON at the given path (or the
default data/catalogs/ai_tell_catalog.json).  Falls back to an empty catalog
if the file doesn't exist so the agent never fails on a missing file.

Pattern format matches the ai_tell_catalog.schema.json:
  categories → patterns → {pattern_id, severity, detection_method, regex_or_rule}

Severity mapping (integer 1-5 → string):
  5 = critical, 4 = high, 3-2 = medium, 1 = info
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class Violation:
    line_number: int
    line_text: str
    matched_phrase: str
    category: str
    severity: str  # "critical" | "high" | "medium" | "info"
    context: str


@dataclass
class ScanReport:
    total_violations: int
    critical_count: int
    high_count: int
    medium_count: int
    violations: list[Violation] = field(default_factory=list)
    is_clean: bool = False

    def get_violation_phrases_for_prompt(self) -> str:
        if self.is_clean:
            return "None — text is clean."
        phrases = sorted({v.matched_phrase for v in self.violations})
        return "SPECIFIC VIOLATIONS TO FIX:\n" + "\n".join(f'  - "{p}"' for p in phrases)


def _severity_label(severity_int: int) -> str:
    if severity_int >= 5:
        return "critical"
    if severity_int >= 4:
        return "high"
    if severity_int >= 2:
        return "medium"
    return "info"


def _build_pattern(phrase: str) -> re.Pattern[str]:
    words = phrase.strip().split()
    if len(words) == 1:
        return re.compile(rf"\b{re.escape(words[0])}\b", re.IGNORECASE)
    inner = r"\s+".join(re.escape(w) for w in words)
    return re.compile(rf"\b{inner}\b", re.IGNORECASE)


# ── NoFlyScanner ──────────────────────────────────────────────────────────────


class NoFlyScanner:
    """Loads an ai_tell_catalog JSON and scans prose for violations."""

    _DEFAULT_CATALOG = Path("data/catalogs/ai_tell_catalog.json")

    def __init__(self, catalog_path: Path | None = None) -> None:
        path = catalog_path or self._DEFAULT_CATALOG
        self._compiled: list[tuple[re.Pattern[str], str, str, str]] = []
        # (pattern, phrase_or_description, category, severity_label)

        if not path.exists():
            return  # empty catalog → scanner always returns clean

        data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
        patterns = data.get("patterns", [])
        if not isinstance(patterns, list):
            return

        for pat in patterns:
            if not isinstance(pat, dict):
                continue
            method = pat.get("detection_method", "")
            regex_or_rule = pat.get("regex_or_rule")
            category = str(pat.get("category", "unknown"))
            sev_label = _severity_label(int(pat.get("severity", 2)))
            description = str(pat.get("pattern_id", ""))

            if method == "regex" and isinstance(regex_or_rule, str):
                try:
                    compiled = re.compile(regex_or_rule, re.IGNORECASE)
                    self._compiled.append((compiled, description, category, sev_label))
                except re.error:
                    pass
            elif method == "rule" and isinstance(regex_or_rule, str):
                self._compiled.append(
                    (_build_pattern(regex_or_rule), regex_or_rule, category, sev_label)
                )

    # ── Public API ─────────────────────────────────────────────────────────

    def scan(self, text: str) -> ScanReport:
        lines = text.split("\n")
        violations: list[Violation] = []

        for line_idx, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            for pattern, phrase, category, sev in self._compiled:
                for match in pattern.finditer(line):
                    violations.append(
                        Violation(
                            line_number=line_idx,
                            line_text=line.strip(),
                            matched_phrase=match.group(0),
                            category=category,
                            severity=sev,
                            context=_extract_context(line, match.start(), match.end()),
                        )
                    )

        # deduplicate by (line, lowercased match)
        seen: set[tuple[int, str]] = set()
        unique: list[Violation] = []
        for v in violations:
            key = (v.line_number, v.matched_phrase.lower())
            if key not in seen:
                seen.add(key)
                unique.append(v)

        sev_order = {"critical": 0, "high": 1, "medium": 2, "info": 3}
        unique.sort(key=lambda v: (v.line_number, sev_order.get(v.severity, 4)))

        critical = sum(1 for v in unique if v.severity == "critical")
        high = sum(1 for v in unique if v.severity == "high")
        medium = sum(1 for v in unique if v.severity == "medium")

        return ScanReport(
            total_violations=len(unique),
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            violations=unique,
            is_clean=len(unique) == 0,
        )


def _extract_context(line: str, start: int, end: int) -> str:
    ctx_start = max(0, start - 40)
    ctx_end = min(len(line), end + 40)
    prefix = "..." if ctx_start > 0 else ""
    suffix = "..." if ctx_end < len(line) else ""
    return f"{prefix}{line[ctx_start:ctx_end]}{suffix}"
