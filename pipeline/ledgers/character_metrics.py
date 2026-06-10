"""Deterministic per-character dialogue metrics.

This is a local V1 fallback for explicit dialogue attribution. BookNLP can
replace the attribution layer later while preserving the output schema.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

_SPEAKER_LINE_RE = re.compile(r"^\s*([A-Z][A-Za-z0-9_-]{1,40})\s*:\s*[\"']?(.*?)[\"']?\s*$")
_TAGGED_DIALOGUE_RE = re.compile(
    r'"([^"\n]+)"\s*,?\s+([A-Z][A-Za-z0-9_-]{1,40})\s+'
    r"(?:said|asked|whispered|muttered|shouted|replied)\b"
)
_WORD_RE = re.compile(r"\b[A-Za-z]+(?:'[A-Za-z]+)?\b")
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")

_FIRST_PERSON = {"i", "me", "my", "mine", "we", "us", "our", "ours"}
_SECOND_PERSON = {"you", "your", "yours"}
_MODALS = {"can", "could", "may", "might", "must", "shall", "should", "will", "would"}
_FUNCTION_WORDS = (
    "the",
    "and",
    "but",
    "or",
    "if",
    "because",
    "that",
    "this",
    "to",
    "of",
    "in",
    "for",
    "with",
)
_POSITIVE_WORDS = {
    "love",
    "like",
    "safe",
    "good",
    "yes",
    "trust",
    "hope",
    "want",
    "warm",
    "happy",
}
_NEGATIVE_WORDS = {
    "hate",
    "no",
    "never",
    "bad",
    "afraid",
    "fear",
    "hurt",
    "angry",
    "cold",
    "wrong",
}


def compute_character_metrics(scene_text: str) -> dict[str, dict[str, Any]]:
    """Compute 12 deterministic dialogue metrics keyed by character ID."""
    utterances = extract_character_utterances(scene_text)
    return {
        speaker: _metrics_for_utterances(lines) for speaker, lines in sorted(utterances.items())
    }


def extract_character_utterances(scene_text: str) -> dict[str, list[str]]:
    """Extract dialogue utterances keyed by speaker from explicit local patterns."""
    utterances: dict[str, list[str]] = defaultdict(list)

    for line in scene_text.splitlines():
        match = _SPEAKER_LINE_RE.match(line)
        if match:
            speaker, dialogue = match.groups()
            if dialogue.strip():
                utterances[_normalize_speaker(speaker)].append(dialogue.strip())

    for dialogue, speaker in _TAGGED_DIALOGUE_RE.findall(scene_text):
        if dialogue.strip():
            utterances[_normalize_speaker(speaker)].append(dialogue.strip())

    return dict(utterances)


def _metrics_for_utterances(utterances: list[str]) -> dict[str, Any]:
    text = " ".join(utterances)
    words = [word.lower() for word in _WORD_RE.findall(text)]
    word_count = len(words)
    sentences = [sentence.strip() for sentence in _SENTENCE_RE.findall(text) if sentence.strip()]
    sentence_count = max(1, len(sentences))
    word_denom = max(1, word_count)
    counts = Counter(words)
    sentiment_scores = [_sentiment(sentence) for sentence in sentences] or [0.0]

    return {
        "mtld": round(_mtld_approx(words), 3),
        "avg_word_length_chars": round(_avg_word_length(words), 3),
        "question_rate": round(text.count("?") / sentence_count, 3),
        "exclamatory_rate": round(text.count("!") / sentence_count, 3),
        "imperative_rate": round(_imperative_count(sentences) / sentence_count, 3),
        "first_person_pronoun_rate": round(_count_any(words, _FIRST_PERSON) / word_denom, 3),
        "second_person_pronoun_rate": round(_count_any(words, _SECOND_PERSON) / word_denom, 3),
        "modal_verb_rate": round(_count_any(words, _MODALS) / word_denom, 3),
        "sentiment_mean": round(statistics.fmean(sentiment_scores), 3),
        "sentiment_std": round(statistics.pstdev(sentiment_scores), 3),
        "fk_grade": round(_fk_grade(words, sentences), 3),
        "function_word_vector": {
            word: round(counts[word] / word_denom, 4) for word in _FUNCTION_WORDS
        },
    }


def _normalize_speaker(speaker: str) -> str:
    return speaker.strip().lower().replace(" ", "_")


def _mtld_approx(words: list[str]) -> float:
    if not words:
        return 0.0
    return (len(set(words)) / len(words)) * min(100.0, math.sqrt(len(words)) * 20.0)


def _avg_word_length(words: list[str]) -> float:
    if not words:
        return 0.0
    return sum(len(word) for word in words) / len(words)


def _imperative_count(sentences: Iterable[str]) -> int:
    imperatives = 0
    for sentence in sentences:
        first_word = _WORD_RE.search(sentence)
        if first_word and first_word.group(0).lower() in {"go", "stop", "look", "listen", "wait"}:
            imperatives += 1
    return imperatives


def _count_any(words: list[str], targets: set[str]) -> int:
    return sum(1 for word in words if word in targets)


def _sentiment(sentence: str) -> float:
    words = [word.lower() for word in _WORD_RE.findall(sentence)]
    if not words:
        return 0.0
    positive = _count_any(words, _POSITIVE_WORDS)
    negative = _count_any(words, _NEGATIVE_WORDS)
    return (positive - negative) / len(words)


def _fk_grade(words: list[str], sentences: list[str]) -> float:
    if not words:
        return 0.0
    sentence_count = max(1, len(sentences))
    syllables = sum(_syllable_count(word) for word in words)
    return max(0.0, 0.39 * (len(words) / sentence_count) + 11.8 * (syllables / len(words)) - 15.59)


def _syllable_count(word: str) -> int:
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return 1
    groups = re.findall(r"[aeiouy]+", cleaned)
    count = len(groups)
    if cleaned.endswith("e") and count > 1:
        count -= 1
    return max(1, count)
