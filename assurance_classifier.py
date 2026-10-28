"""Classify what a third-party review or assurance statement explicitly says.

Reads only the statement text. Never infers the assurance type, level, scope, metric or
period from a reviewer's name or from context outside the text. Anything not stated is
returned as UNKNOWN / None / missing.

Assurance is metadata about a statement. It is NOT proof that an environmental claim is
true, and it is NOT evidence that a source is independent of the company.
"""

from __future__ import annotations

import re

LIMITED_ASSURANCE = "limited_assurance"
REASONABLE_ASSURANCE = "reasonable_assurance"
LIMITED_REVIEW = "limited_review_unspecified_assurance"
AGREED_UPON_PROCEDURES = "agreed_upon_procedures"
REVIEW_UNSPECIFIED = "review_unspecified"
NOT_ASSURANCE = "company_authored_no_third_party"
UNKNOWN = "unknown"

LEVEL_LIMITED = "limited"
LEVEL_REASONABLE = "reasonable"
LEVEL_NOT_ASSURANCE = "no_assurance_level"
LEVEL_UNKNOWN = "unknown"

STATUS_VERIFIED = "verified"
STATUS_UNVERIFIED = "unverified"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_MISSING = "missing"
STATUS_MALFORMED = "malformed"
STATUS_NOT_ASSURANCE = "not_assurance"

NOT_PROOF_OF_CLAIM_TRUTH = "Assurance is not proof that any environmental claim is true."
NOT_PROOF_OF_INDEPENDENCE = "Assurance is not evidence that a source is independent of the company."

_TYPE_PATTERNS = [
    (REASONABLE_ASSURANCE, re.compile(r"\breasonable\s+assurance\b", re.I)),
    (LIMITED_ASSURANCE, re.compile(r"\blimited\s+assurance\b", re.I)),
    (AGREED_UPON_PROCEDURES, re.compile(r"\bagreed[- ]upon\s+procedures\b", re.I)),
    (LIMITED_REVIEW, re.compile(r"\blimited\s+review\b", re.I)),
]
_REVIEWER_HINT = re.compile(r"\b(?:review(?:ed|er)?|assur(?:ed|ance) provider|independent (?:review|assurance))\b", re.I)
_NEGATION = re.compile(r"\b(?:not|no|never|without|neither|nor)\b", re.I)
_SCOPE_MENTION = re.compile(r"\bscopes?\s+((?:[123]|,|\s|&|and)+)", re.I)
_PERIOD = re.compile(
    r"\b(?:fiscal\s+year|FY)\s*['’]?((?:19|20)\d{2})\b"
    r"|\byear[- ]ended\s+(?:[A-Za-z]+\s+\d{1,2},?\s+)?((?:19|20)\d{2})\b",
    re.I,
)
_EXCLUSION = re.compile(
    r"\bnot\s+(?:subject|covered|included|within)\b"
    r"|\b(?:excluded|excludes|excluding)\b"
    r"|\boutside\s+(?:the\s+|our\s+)?(?:scope|review|assurance)\b",
    re.I,
)
_ASSURANCE_WORD = re.compile(r"\b(?:assurance|assured|review|reviewed|reviewer|verif\w*|audited|procedures)\b", re.I)
_METRIC_TERMS = [
    "emissions", "electricity", "energy", "water", "waste", "renewable", "carbon", "greenhouse gas",
]
_METRIC_PATTERNS = [(term, re.compile(r"\b" + re.escape(term) + r"\b", re.I)) for term in _METRIC_TERMS]
_CLAUSE_SPLIT = re.compile(r"(?<=[.;])\s+")
_BASELINE_YEAR = re.compile(
    r"\b(?P<year_before>(?:19|20)\d{2})\s+baseline\b"
    r"|\b(?:baseline|base year)(?:\s+year)?\s*"
    r"(?:of|is|was|:)?\s*['’]?(?P<year_after>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)


def _empty_result(status, reason):
    return {
        "assurance_type": UNKNOWN,
        "assurance_level": LEVEL_UNKNOWN,
        "scopes_covered": [],
        "scopes_excluded": [],
        "metrics_covered": [],
        "period": None,
        "baseline_years": [],
        "exclusions": [],
        "has_exclusion_language": False,
        "status": status,
        "reason": reason,
    }


def _is_negated(clause, match_start):
    """True when a negation word appears before the match in the same clause."""
    return bool(_NEGATION.search(clause[:match_start]))


def classify_assurance(text):
    """Return a dict describing only what the text states."""
    if text is None:
        return _empty_result(UNKNOWN, "No assurance text provided.")
    if not isinstance(text, str):
        return _empty_result(STATUS_MALFORMED, "Assurance text is not a string; nothing was inferred from it.")
    if not text.strip():
        return _empty_result(UNKNOWN, "No assurance text provided.")

    result = _empty_result(UNKNOWN, "")
    clauses = [clause for clause in _CLAUSE_SPLIT.split(text) if clause.strip()]

    stated_types = set()
    negated_only = False
    for name, pattern in _TYPE_PATTERNS:
        for clause in clauses:
            for match in pattern.finditer(clause):
                if _is_negated(clause, match.start()):
                    negated_only = True
                else:
                    stated_types.add(name)

    if len(stated_types) > 1:
        result["status"] = "ambiguous_assurance_type"
        result["reason"] = "Text states more than one assurance type; no single type can be assigned."
    elif stated_types:
        result["assurance_type"] = next(iter(stated_types))
    elif _REVIEWER_HINT.search(text):
        result["assurance_type"] = REVIEW_UNSPECIFIED
        result["status"] = "reviewer_named_without_stated_assurance_type"
        result["reason"] = "A review is mentioned but the text does not state an assurance type."
    else:
        result["assurance_type"] = NOT_ASSURANCE
        result["status"] = "no_third_party_assurance_stated"
        result["reason"] = "No third-party assurance or review language found."
    if negated_only and not stated_types:
        result["reason"] += " An assurance type phrase appears only in negated form and is not counted."

    for clause in clauses:
        clause_excluded = bool(_EXCLUSION.search(clause))
        result["has_exclusion_language"] = result["has_exclusion_language"] or clause_excluded
        if clause_excluded:
            result["exclusions"].append(clause.strip())
        # A scope is only assigned from a clause that also names assurance or review, so a
        # bare scope mention elsewhere in the text is not treated as covered.
        if not _ASSURANCE_WORD.search(clause) and not clause_excluded:
            continue
        for listed in _SCOPE_MENTION.finditer(clause):
            numbers = re.findall(r"[123]", listed.group(1))
            target = result["scopes_excluded"] if clause_excluded else result["scopes_covered"]
            for number in numbers:
                label = f"Scope {number}"
                if label not in target:
                    target.append(label)
        if not clause_excluded:
            lowered = clause.casefold()
            for term, pattern in _METRIC_PATTERNS:
                if pattern.search(lowered) and term not in result["metrics_covered"]:
                    result["metrics_covered"].append(term)

    # Conservative: a scope that is both covered and excluded is treated as excluded.
    result["scopes_covered"] = [s for s in result["scopes_covered"] if s not in result["scopes_excluded"]]
    if result["assurance_type"] == NOT_ASSURANCE:
        # No third-party assurance is stated, so no scope or metric can be attributed to one.
        result["scopes_covered"], result["scopes_excluded"], result["metrics_covered"] = [], [], []

    years = {match.group(1) or match.group(2) for match in _PERIOD.finditer(text)}
    if len(years) == 1:
        result["period"] = next(iter(years))
    elif len(years) > 1:
        result["period"] = None
        result["period_ambiguous"] = sorted(years)

    result["baseline_years"] = sorted({
        match.group("year_before") or match.group("year_after")
        for match in _BASELINE_YEAR.finditer(text)
    })

    if result["assurance_type"] in {LIMITED_ASSURANCE, REASONABLE_ASSURANCE, LIMITED_REVIEW, AGREED_UPON_PROCEDURES} and result["status"] == UNKNOWN:
        result["status"] = "stated_assurance"
        result["reason"] = "Assurance type stated."
    return result


def _level_for(assurance_type):
    if assurance_type == LIMITED_ASSURANCE:
        return LEVEL_LIMITED
    if assurance_type == REASONABLE_ASSURANCE:
        return LEVEL_REASONABLE
    if assurance_type == AGREED_UPON_PROCEDURES:
        return LEVEL_NOT_ASSURANCE
    if assurance_type == NOT_ASSURANCE:
        return LEVEL_NOT_ASSURANCE
    return LEVEL_UNKNOWN


def build_assurance_record(text, provider="", source_url="", stated_period_text=None):
    """Build one explicit, source-linked assurance record. Missing facts stay None.

    provider, source_url and stated_period_text must come from the source itself; they are
    recorded as given (blank becomes None) and are never filled in from the text.
    """
    classification = classify_assurance(text)
    provider = str(provider).strip() if isinstance(provider, str) and provider.strip() else None
    source_url = str(source_url).strip() if isinstance(source_url, str) and source_url.strip() else None
    stated_period_text = (
        stated_period_text.strip()
        if isinstance(stated_period_text, str) and stated_period_text.strip()
        else None
    )
    assurance_type = classification["assurance_type"]
    level = _level_for(assurance_type)
    raw_status = classification["status"]

    missing = []
    if provider is None:
        missing.append("provider")
    if source_url is None:
        missing.append("source_url")
    if classification["period"] is None and stated_period_text is None:
        missing.append("reporting_period")
    if not classification["scopes_covered"] and not classification["scopes_excluded"]:
        missing.append("scope")
    if not classification["metrics_covered"]:
        missing.append("metrics")

    if raw_status == STATUS_MALFORMED:
        status = STATUS_MALFORMED
    elif raw_status == "ambiguous_assurance_type":
        status = STATUS_AMBIGUOUS
    elif assurance_type == NOT_ASSURANCE:
        status = STATUS_NOT_ASSURANCE
    elif assurance_type == UNKNOWN:
        status = STATUS_MISSING
    elif provider is None or source_url is None:
        status = STATUS_MISSING
    elif level in {LEVEL_LIMITED, LEVEL_REASONABLE}:
        status = STATUS_VERIFIED
    else:
        status = STATUS_UNVERIFIED

    reason = classification["reason"]
    if status == STATUS_MISSING and provider is None:
        reason = (reason + " No assurance provider is attributed in the source.").strip()
    if source_url is None:
        reason = (reason + " No source URL is recorded.").strip()
    if classification.get("period_ambiguous"):
        reason = (reason + " More than one fiscal year is stated; no single period is assigned.").strip()

    return {
        "status": status,
        "provider": provider,
        "source_url": source_url,
        "assurance_type": assurance_type,
        "assurance_level": level,
        "scopes_covered": list(classification["scopes_covered"]),
        "scopes_excluded": list(classification["scopes_excluded"]),
        "metrics_covered": list(classification["metrics_covered"]),
        "reporting_period": classification["period"],
        "reporting_period_text": stated_period_text,
        "baseline_years": list(classification["baseline_years"]),
        "exclusions": list(classification["exclusions"]),
        "rationale": reason,
        "missing_fields": missing,
        "limitations": [NOT_PROOF_OF_CLAIM_TRUTH, NOT_PROOF_OF_INDEPENDENCE],
    }


def assurance_supports_scope(classification, claim_scopes):
    """True only when every claimed scope is explicitly covered and none is excluded."""
    covered = set(classification.get("scopes_covered") or [])
    excluded = set(classification.get("scopes_excluded") or [])
    wanted = {f"Scope {s}" for s in claim_scopes}
    if not wanted:
        return False
    return wanted <= covered and not (wanted & excluded)


_STATUS_TEXT = {
    STATUS_VERIFIED: None,  # built from the level below
    STATUS_UNVERIFIED: "Third-party review; assurance level not stated",
    STATUS_AMBIGUOUS: "Ambiguous assurance statement; no single type assigned",
    STATUS_MISSING: "Assurance details missing from the source",
    STATUS_MALFORMED: "Malformed assurance record",
    STATUS_NOT_ASSURANCE: "Company-authored; no third-party assurance stated",
}
_LEVEL_TEXT = {LEVEL_LIMITED: "Limited assurance", LEVEL_REASONABLE: "Reasonable assurance"}


def summarize_assurance_record(record):
    """One-line, display-only summary of a stored assurance record.

    Missing, older or malformed records are described as such. Nothing is inferred.
    """
    if record is None:
        return "Not assessed (no assurance record stored)"
    if not isinstance(record, dict):
        return "Malformed assurance record"
    status = record.get("status")
    if status not in _STATUS_TEXT:
        return "Malformed assurance record"
    provider = record.get("provider") or "provider not stated"
    if status == STATUS_VERIFIED:
        head = f"{_LEVEL_TEXT.get(record.get('assurance_level'), 'Assurance')} by {provider}"
    elif status == STATUS_UNVERIFIED:
        head = f"Third-party review by {provider}; assurance level not stated"
    else:
        head = _STATUS_TEXT[status]
    details = []
    if record.get("scopes_covered"):
        details.append("covers " + ", ".join(record["scopes_covered"]))
    if record.get("scopes_excluded"):
        details.append("excludes " + ", ".join(record["scopes_excluded"]))
    if record.get("reporting_period"):
        details.append(f"period {record['reporting_period']}")
    elif record.get("reporting_period_text"):
        details.append(str(record["reporting_period_text"]))
    return head + (f" ({'; '.join(details)})" if details else "")
