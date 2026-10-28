"""Extraction-quality status for a statement extracted from a document.

The original text is never changed. The status tells downstream matching whether the
text is usable as evidence. A malformed or incomplete statement must not become strong
support because of high semantic similarity.

USABLE      - readable sentence with context; may still be irrelevant to a claim.
INCOMPLETE  - readable but truncated, a table fragment without headers, or missing units.
MALFORMED   - concatenated headings, page furniture, broken encoding, dot-leader noise.
"""

from __future__ import annotations

import re

USABLE, INCOMPLETE, MALFORMED = "USABLE", "INCOMPLETE", "MALFORMED"

_REPLACEMENT = "\ufffd"
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_PAGE_FURNITURE = re.compile(
    r"\bpage\s+\d+\s+(?:of|/)\s+\d+\b|\bpage\s+\d+\b|\bcontinued\b|\bsee\s+page\b",
    re.IGNORECASE,
)
_DOT_LEADER = re.compile(r"(?:\s?\.\s?){4,}")
_CONCATENATED = re.compile(r"[A-Za-z]{30,}")  # long run with no spaces
_CAMEL_RUN = re.compile(r"(?:[a-z]+[A-Z][a-z]+){4,}")
_HYPHEN_BREAK = re.compile(r"[a-z]{2,}-\s+[a-z]{2,}\b")  # e.g. "emis- sions"
_NUMBER = re.compile(r"\d")
_DANGLING_WORDS = {"with", "and", "or", "of", "in", "to", "by", "from", "for", "than", "versus", "vs", "as", "at", "on"}


def assess_statement_quality(text):
    """Return (status, reasons). Never modifies the text."""
    original = str(text or "")
    reasons = []
    if not original.strip():
        return INCOMPLETE, ["empty statement"]

    if _REPLACEMENT in original or _CONTROL.search(original):
        return MALFORMED, ["broken encoding or control characters"]
    if _CONCATENATED.search(original) or _CAMEL_RUN.search(original):
        return MALFORMED, ["concatenated heading or run-together words"]
    if _DOT_LEADER.search(original):
        return MALFORMED, ["table dot-leader fragment"]
    if _PAGE_FURNITURE.search(original) and len(original.split()) < 12:
        return MALFORMED, ["page navigation or header/footer text"]
    if _HYPHEN_BREAK.search(original):
        reasons.append("possible hyphenation break; wording may be split")

    words = original.split()
    if len(words) < 4 and not _NUMBER.search(original):
        return INCOMPLETE, reasons + ["too short and contains no figure"]
    if original.count(" ") == 0:
        return INCOMPLETE, reasons + ["single token"]
    if len(words) >= 4 and sum(1 for w in words if _NUMBER.search(w)) / len(words) > 0.6:
        return INCOMPLETE, reasons + ["mostly numbers; table fragment without context"]
    last_word = re.sub(r"[^a-z]", "", words[-1].casefold()) if words else ""
    dangling = last_word in _DANGLING_WORDS
    if dangling or (not original.rstrip().endswith((".", "!", "?", "%", ")")) and len(words) < 8):
        reasons.append("appears truncated")
        return INCOMPLETE, reasons

    return USABLE, reasons or ["readable"]
