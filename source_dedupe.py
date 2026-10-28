"""Deterministic and conservative duplicate-source detection.

Exact duplicates are found by hash. Near duplicates need a high word-shingle overlap AND
identical numeric content, so two different reporting years, revised figures or separate
assurance statements are never merged on text similarity alone. Results are grouping
annotations; they do not delete candidates.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urldefrag, urlsplit, urlunsplit

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid", "gclid", "ref"}
NEAR_DUPLICATE_THRESHOLD = 0.90
SHINGLE_SIZE = 5


def normalize_url(url):
    """Canonical comparison form of a URL. Does not fetch anything."""
    url = str(url or "").strip()
    if not url:
        return ""
    url, _ = urldefrag(url)
    parts = urlsplit(url)
    host = parts.netloc.casefold()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    query = urlencode(sorted(
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.casefold() not in TRACKING_PARAMS
    ))
    return urlunsplit(("https", host, path, query, ""))


def _normalize_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def content_fingerprint(text):
    """SHA-256 of whitespace- and case-normalized text. Exact duplicates only."""
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def _shingles(text):
    words = re.findall(r"[a-z0-9]+(?:[.,%][0-9]+)?", _normalize_text(text))
    if len(words) < SHINGLE_SIZE:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i + SHINGLE_SIZE]) for i in range(len(words) - SHINGLE_SIZE + 1)}


def _numbers(text):
    return sorted(set(re.findall(r"\d[\d,]*(?:\.\d+)?", str(text or ""))))


def near_duplicate(text_a, text_b):
    """Conservative: high shingle overlap AND identical numbers AND identical year tokens."""
    if _numbers(text_a) != _numbers(text_b):
        return False, 0.0
    years_a = set(re.findall(r"\b(?:19|20)\d{2}\b", str(text_a)))
    years_b = set(re.findall(r"\b(?:19|20)\d{2}\b", str(text_b)))
    if years_a != years_b:
        return False, 0.0
    a, b = _shingles(text_a), _shingles(text_b)
    if not a or not b:
        return False, 0.0
    overlap = len(a & b) / len(a | b)
    return overlap >= NEAR_DUPLICATE_THRESHOLD, round(overlap, 3)


def _host(canonical):
    return urlsplit(canonical).netloc if canonical else ""


def _relation(item, rep):
    """Return (relation, method, confidence) between a candidate and a representative.

    relation is one of:
      duplicate              - same document; excluded from further evaluation
      potentially_related    - similar content, relationship NOT established; kept
      None                   - no relationship signal

    Only same-document signals or an explicit provenance link create a duplicate.
    Identical figures, years or wording across different sites never do.
    """
    text_a, text_b = item["_text"], rep["_text"]
    canon_a, canon_b = item["canonical_url"], rep["canonical_url"]
    origin_a = item.get("_origin") or ""
    origin_b = rep.get("_origin") or ""

    # 1. An explicit provenance link: both point at the same original publication, or
    #    one is the original of the other. This is the only syndication signal.
    if origin_a and origin_b and origin_a == origin_b:
        return "duplicate", "shared_original_source", 0.95
    if origin_a and origin_a == canon_b:
        return "duplicate", "original_source_link", 0.95
    if origin_b and origin_b == canon_a:
        return "duplicate", "original_source_link", 0.95

    same_url = bool(canon_a) and canon_a == canon_b
    if item["content_fingerprint"] == rep["content_fingerprint"]:
        if same_url:
            return "duplicate", "exact_content_same_url", 1.0
        if _host(canon_a) and _host(canon_a) == _host(canon_b):
            return "duplicate", "exact_content_same_site", 1.0
        return "potentially_related", "identical_text_different_site", 1.0

    ok, score = near_duplicate(text_a, text_b)
    if ok:
        if same_url:
            return "duplicate", "same_url_near_duplicate", score
        # Different URLs: separate documents, even on one site and with the same figures.
        return "potentially_related", "near_duplicate_different_url", score
    return None, None, None


def group_candidates(candidates):
    """Annotate candidate dicts with duplicate and relation information. Returns the same list.

    Fields: content_fingerprint, canonical_url, duplicate_group_id, duplicate_method,
    duplicate_confidence, is_duplicate_of (set only for duplicates), source_relation
    ("representative" | "duplicate" | "potentially_related"), potentially_related_to.
    Nothing is deleted. Duplicate relations require a same-document signal.
    """
    representatives = []  # dicts with group id, text, canonical, fingerprint
    for index, item in enumerate(candidates):
        text = item.get("statement") or item.get("matched_evidence") or ""
        canonical = normalize_url(item.get("source_url") or item.get("final_url") or "")
        fingerprint = content_fingerprint(text)
        item["content_fingerprint"] = fingerprint
        item["canonical_url"] = canonical
        item["duplicate_group_id"] = None
        item["duplicate_method"] = None
        item["duplicate_confidence"] = None
        item["is_duplicate_of"] = None
        item["source_relation"] = "representative"
        item["potentially_related_to"] = None
        current = {
            "_text": text,
            "_origin": normalize_url(item.get("original_source_url") or ""),
            "canonical_url": canonical,
            "content_fingerprint": fingerprint,
        }
        duplicate_of, related_to = None, None
        for rep in representatives:
            relation, method, confidence = _relation(current, rep)
            if relation == "duplicate" and duplicate_of is None:
                duplicate_of = (rep["group_id"], method, confidence)
            elif relation == "potentially_related" and related_to is None:
                related_to = (rep["group_id"], method, confidence)
        if duplicate_of:
            group_id, method, confidence = duplicate_of
            item["duplicate_group_id"] = group_id
            item["duplicate_method"] = method
            item["duplicate_confidence"] = confidence
            item["is_duplicate_of"] = group_id
            item["source_relation"] = "duplicate"
        else:
            group_id = f"grp-{index + 1}"
            item["duplicate_group_id"] = group_id
            if related_to:
                item["potentially_related_to"] = related_to[0]
                item["duplicate_method"] = related_to[1]
                item["duplicate_confidence"] = related_to[2]
                item["source_relation"] = "potentially_related"
            representatives.append({
                "group_id": group_id, "_text": text, "_origin": current["_origin"],
                "canonical_url": canonical, "content_fingerprint": fingerprint,
            })
    return candidates


def is_representative(item):
    """True for the first member of a group; duplicates carry is_duplicate_of."""
    return item.get("is_duplicate_of") is None
