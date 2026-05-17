"""StructuralAnalyzer — deterministic structural AI-tell detector.

Ported and adapted from manus-agnostic structural_analysis.py.
Detects: burstiness, em-dash density, ellipsis overuse, contrast sentence
patterns, sentence opener monotony, and paragraph-ending summary patterns.

All checks are deterministic (regex + counting). No LLM calls.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class StructuralIssue:
    check_name: str
    severity: str  # "critical" | "high" | "medium" | "info"
    location: str
    detail: str
    offending_text: str


@dataclass
class StructuralReport:
    issues: list[StructuralIssue] = field(default_factory=list)
    stats: dict[str, float] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.issues)

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0

    def weighted_score(self) -> int:
        weights = {"critical": 3, "high": 2, "medium": 1, "info": 0}
        return sum(weights.get(i.severity, 1) for i in self.issues)

    def get_issues_for_prompt(self) -> str:
        if self.is_clean:
            return "No structural issues found."
        lines = [f"STRUCTURAL ISSUES TO ADDRESS ({len(self.issues)} total):"]
        for i in self.issues:
            lines.append(f"  [{i.severity.upper()}] {i.check_name}: {i.detail}")
            if i.offending_text:
                lines.append(f"    Example: {i.offending_text[:120]}")
        return "\n".join(lines)


# ── Thresholds ────────────────────────────────────────────────────────────────

_EM_DASH_PER_1K_THRESHOLD = 8.0
_ELLIPSIS_PER_1K_THRESHOLD = 4.0
_BURSTINESS_CONSECUTIVE = 3  # consecutive sentences within ±2 words → flag
_OPENER_MONOTONY_THRESHOLD = 0.40  # 40% same pattern → flag


# ── StructuralAnalyzer ────────────────────────────────────────────────────────


class StructuralAnalyzer:
    """Run all deterministic structural checks on prose text."""

    def analyze(self, text: str) -> StructuralReport:
        report = StructuralReport()
        words = text.split()
        word_count = max(len(words), 1)
        per_1k = word_count / 1000.0

        self._check_burstiness(text, report)
        self._check_em_dash_density(text, word_count, per_1k, report)
        self._check_ellipsis_overuse(text, word_count, per_1k, report)
        self._check_contrast_sentence(text, report)
        self._check_opener_monotony(text, report)
        self._check_paragraph_ending_summary(text, report)

        report.stats["word_count"] = float(word_count)
        report.stats["em_dash_count"] = float(text.count("—") + text.count("–"))
        report.stats["ellipsis_count"] = float(text.count("...") + text.count("…"))

        return report

    # ── Checks ────────────────────────────────────────────────────────────

    def _check_burstiness(self, text: str, report: StructuralReport) -> None:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        for para_idx, para in enumerate(paragraphs, start=1):
            sentences = _split_sentences(para)
            if len(sentences) < _BURSTINESS_CONSECUTIVE:
                continue
            lengths = [len(s.split()) for s in sentences]
            run = 1
            for i in range(1, len(lengths)):
                if abs(lengths[i] - lengths[i - 1]) <= 2:
                    run += 1
                    if run >= _BURSTINESS_CONSECUTIVE:
                        report.issues.append(
                            StructuralIssue(
                                check_name="burstiness",
                                severity="medium",
                                location=f"paragraph {para_idx}",
                                detail=(
                                    f"{run} consecutive sentences within ±2 words "
                                    f"(lengths: {lengths[i - run + 1 : i + 1]})"
                                ),
                                offending_text=sentences[i][:100],
                            )
                        )
                        break
                else:
                    run = 1

    def _check_em_dash_density(
        self, text: str, word_count: int, per_1k: float, report: StructuralReport
    ) -> None:
        count = text.count("—") + text.count("–")
        if per_1k > 0 and (count / per_1k) > _EM_DASH_PER_1K_THRESHOLD:
            report.issues.append(
                StructuralIssue(
                    check_name="em_dash_density",
                    severity="medium",
                    location="document-level",
                    detail=(
                        f"{count} em/en dashes in {word_count} words "
                        f"({count / per_1k:.1f}/1k, threshold={_EM_DASH_PER_1K_THRESHOLD})"
                    ),
                    offending_text="",
                )
            )

    def _check_ellipsis_overuse(
        self, text: str, word_count: int, per_1k: float, report: StructuralReport
    ) -> None:
        count = text.count("...") + text.count("…")
        if per_1k > 0 and (count / per_1k) > _ELLIPSIS_PER_1K_THRESHOLD:
            report.issues.append(
                StructuralIssue(
                    check_name="ellipsis_overuse",
                    severity="medium",
                    location="document-level",
                    detail=(
                        f"{count} ellipses in {word_count} words "
                        f"({count / per_1k:.1f}/1k, threshold={_ELLIPSIS_PER_1K_THRESHOLD})"
                    ),
                    offending_text="",
                )
            )

    def _check_contrast_sentence(self, text: str, report: StructuralReport) -> None:
        pattern = re.compile(
            r"(?:It(?:'s| is) not [^.!?]+\.)\s+(?:It(?:'s| is) [^.!?]+\.)"
            r"|(?:Not because [^.!?]+\.)\s+(?:Because [^.!?]+\.)",
            re.IGNORECASE,
        )
        for m in pattern.finditer(text):
            report.issues.append(
                StructuralIssue(
                    check_name="contrast_sentence_pattern",
                    severity="high",
                    location="inline",
                    detail="AI structural tell: 'Not X. X.' contrast pattern.",
                    offending_text=m.group(0)[:120],
                )
            )

    def _check_opener_monotony(self, text: str, report: StructuralReport) -> None:
        sentences = _split_sentences(text)
        if len(sentences) < 5:
            return
        openers: list[str] = []
        she_he = re.compile(r"^(She|He)\b", re.IGNORECASE)
        the_noun = re.compile(r"^The\b", re.IGNORECASE)
        for s in sentences:
            stripped = s.strip()
            if not stripped:
                continue
            if she_he.match(stripped):
                openers.append("she_he")
            elif the_noun.match(stripped):
                openers.append("the_noun")
            else:
                openers.append("other")
        if not openers:
            return
        c = Counter(openers)
        for pattern_name, count in c.items():
            if pattern_name == "other":
                continue
            ratio = count / len(openers)
            if ratio >= _OPENER_MONOTONY_THRESHOLD:
                report.issues.append(
                    StructuralIssue(
                        check_name="opener_monotony",
                        severity="medium",
                        location="document-level",
                        detail=(
                            f"{count}/{len(openers)} sentences "
                            f"({ratio:.0%}) start with '{pattern_name}' pattern."
                        ),
                        offending_text="",
                    )
                )
                break

    def _check_paragraph_ending_summary(self, text: str, report: StructuralReport) -> None:
        summary_pattern = re.compile(
            r"\b(?:it was|this was|that was|everything was|nothing was|"
            r"something about|somehow|in that moment)\b[^.!?]*[.!?]$",
            re.IGNORECASE,
        )
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        for para_idx, para in enumerate(paragraphs, start=1):
            last_sentence = _last_sentence(para)
            if summary_pattern.search(last_sentence):
                report.issues.append(
                    StructuralIssue(
                        check_name="paragraph_ending_summary",
                        severity="medium",
                        location=f"paragraph {para_idx} ending",
                        detail="AI tell: paragraph ends with summary/abstraction, not action.",
                        offending_text=last_sentence[:120],
                    )
                )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _split_sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", text.strip())


def _last_sentence(para: str) -> str:
    sentences = _split_sentences(para)
    return sentences[-1] if sentences else ""


# Module-level convenience function matching the manus-agnostic interface
def analyze(text: str) -> StructuralReport:
    return StructuralAnalyzer().analyze(text)
