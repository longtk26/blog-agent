import re
from typing import Sequence

from src.modules.shared.domain.entities import IssueSeverity, ValidationIssue


def _extract_prose_words(text: str) -> list[str]:
    """Strip code fences, inline code, and blockquotes, then extract lowercase words."""
    # Remove fenced code blocks
    cleaned = re.sub(r"```[\s\S]*?```", " ", text)
    cleaned = re.sub(r"~~~[\s\S]*?~~~", " ", cleaned)

    # Remove blockquotes and inline code
    lines: list[str] = []
    for line in cleaned.split("\n"):
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"`[^`]+`", " ", cleaned)

    return re.findall(r"\b[a-zA-Z0-9_-]+\b", cleaned.lower())


def _word_ngrams(words: Sequence[str], n: int = 8) -> set[tuple[str, ...]]:
    if len(words) < n:
        return set()
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def _longest_common_subsequence_run(words1: Sequence[str], words2: Sequence[str]) -> int:
    """Find the length of the longest contiguous run of identical words."""
    if not words1 or not words2:
        return 0
    # Rolling window check for long runs
    words2_set = set(words2)
    max_run = 0
    current_run = 0

    # Build index of word positions in words2
    pos2: dict[str, list[int]] = {}
    for idx, w in enumerate(words2):
        pos2.setdefault(w, []).append(idx)

    for i, w in enumerate(words1):
        if w in pos2:
            for j in pos2[w]:
                # Measure run length
                k = 0
                while (
                    i + k < len(words1)
                    and j + k < len(words2)
                    and words1[i + k] == words2[j + k]
                ):
                    k += 1
                if k > max_run:
                    max_run = k
        if max_run >= 100:  # Fast exit on huge run
            break

    return max_run


def check_copy_overlap(
    draft_section_text: str,
    reference_texts: list[str],
    reference_type: str = "sample",  # "sample" or "source"
    section_name: str | None = None,
    ngram_size: int = 8,
    warn_threshold: float = 0.15,
    block_threshold: float = 0.30,
    max_run_words: int = 40,
) -> list[ValidationIssue]:
    """Check for word 8-gram overlap and verbatim word runs between draft and reference texts.

    Code blocks and blockquotes/citations are excluded.
    """
    draft_words = _extract_prose_words(draft_section_text)
    if len(draft_words) < ngram_size:
        return []

    draft_ngrams = _word_ngrams(draft_words, n=ngram_size)
    if not draft_ngrams:
        return []

    # Aggregate reference words and ngrams
    ref_ngrams: set[tuple[str, ...]] = set()
    ref_all_words: list[str] = []
    for ref in reference_texts:
        words = _extract_prose_words(ref)
        if words:
            ref_all_words.extend(words)
            ref_ngrams.update(_word_ngrams(words, n=ngram_size))

    if not ref_ngrams:
        return []

    # Calculate 8-gram overlap
    matching_ngrams = draft_ngrams.intersection(ref_ngrams)
    overlap_ratio = len(matching_ngrams) / len(draft_ngrams)

    # Calculate longest identical word run
    longest_run = _longest_common_subsequence_run(draft_words, ref_all_words)

    issues: list[ValidationIssue] = []
    rule_name = f"copy_detection_{reference_type}"

    pct = int(overlap_ratio * 100)
    if overlap_ratio >= block_threshold:
        issues.append(
            ValidationIssue(
                rule=rule_name,
                severity=IssueSeverity.BLOCKER,
                message=(
                    f"Section has {pct}% verbatim {ngram_size}-gram overlap with {reference_type} texts "
                    f"(limit: {int(block_threshold * 100)}%). Please rewrite in original words."
                ),
                section=section_name,
            )
        )
    elif overlap_ratio >= warn_threshold or longest_run >= max_run_words:
        msg_parts = []
        if overlap_ratio >= warn_threshold:
            msg_parts.append(f"{pct}% verbatim {ngram_size}-gram overlap (warn limit: {int(warn_threshold * 100)}%)")
        if longest_run >= max_run_words:
            msg_parts.append(f"consecutive run of {longest_run} identical words (max: {max_run_words})")
        msg = f"Possible copied text from {reference_type}: " + ", ".join(msg_parts) + "."
        issues.append(
            ValidationIssue(
                rule=rule_name,
                severity=IssueSeverity.WARNING,
                message=msg,
                section=section_name,
            )
        )

    return issues
