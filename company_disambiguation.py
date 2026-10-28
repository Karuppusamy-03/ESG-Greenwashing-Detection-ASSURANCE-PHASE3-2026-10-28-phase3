"""Company-name homonym checks, driven by per-company configuration.

A company name can also be an ordinary word ("Apple" the fruit, "Shell" the seashell).
A search result that uses the word in an unrelated sense must not be treated as a
company mention. The mechanism is the same for every company; only the configuration
differs. Configuration describes vocabulary (homonym context, company context, product
context, legal-name forms). It does not decide whether a claim is true or evidence is
compatible.
"""

from __future__ import annotations

import re

# Each entry: the normalized company key, the ordinary-word token, and the vocabulary.
HOMONYM_CONFIG = {
    "apple": {
        "token": "apple",
        "homonym_context": {
            "activity", "activities", "canned", "canning", "food", "fruit", "fruits",
            "friends", "game", "games", "orchard", "preserved", "preserves", "quiz",
            "quizzes", "student", "students", "vegetable", "vegetables", "juice", "produce",
        },
        "company_context": {
            "corporate", "inc", "incorporated", "manufacturer", "supplier", "business",
            "operations", "facilities", "cupertino",
        },
        "product_context": {"iphone", "ipad", "macbook", "mac", "watch", "ios"},
        "legal_name_forms": r"\bapple\s+(?:incorporated|inc\.?|computer)\b|\bapple['’]s\b",
    },
    "shell": {
        "token": "shell",
        "homonym_context": {"seashell", "seashells", "beach", "beaches", "sea", "coastal", "egg", "eggs", "nut", "nuts"},
        "company_context": {"plc", "oil", "energy", "refinery", "refineries", "petrol", "fuel", "gas", "company", "operations"},
        "product_context": {"lubricant", "lubricants", "fuelcard", "station", "stations"},
        "legal_name_forms": r"\bshell\s+(?:plc|energy|oil)\b|\bshell['’]s\b",
    },
}


def normalize_key(name):
    return re.sub(r"[^a-z0-9]+", "", str(name or "").casefold())


def is_ambiguous_company_mention(company_key, *text_parts, config=None):
    """True when a text uses the company's ordinary-word name without company context."""
    config = config if config is not None else HOMONYM_CONFIG
    entry = config.get(normalize_key(company_key))
    if not entry:
        return False

    text = " ".join(str(part or "") for part in text_parts).casefold()
    tokens = re.findall(r"[a-z0-9]+", text)
    token = entry["token"]
    if token not in tokens or not entry["homonym_context"].intersection(tokens):
        return False

    positions = [index for index, value in enumerate(tokens) if value == token]
    has_nearby_company_context = any(
        entry["company_context"].intersection(tokens[max(0, index - 5):index + 6])
        for index in positions
    )
    has_product_context = bool(entry["product_context"].intersection(tokens))
    has_company_name_form = bool(re.search(entry["legal_name_forms"], text))
    return not (has_nearby_company_context or has_product_context or has_company_name_form)
