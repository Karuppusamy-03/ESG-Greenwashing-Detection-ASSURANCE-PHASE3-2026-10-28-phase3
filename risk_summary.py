"""One analysis-level risk label, shared by every place that displays it.

Row-level categories (one per claim) are aggregated here with a single rule, so the
dashboard, the experimental-prediction line and any saved summary cannot disagree.
Rule: the highest category among rows that were actually predicted. If no row was
predicted, the analysis is NOT_PREDICTED. This is an experimental review signal,
not a finding of greenwashing.
"""

from __future__ import annotations

PREDICTED_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
NOT_PREDICTED = "NOT_PREDICTED"


def analysis_risk_category(features):
    """Return the analysis-level category for a list of feature rows."""
    predicted = [
        str(item.get("demonstration_risk_category") or "")
        for item in (features or [])
        if isinstance(item, dict)
    ]
    ranked = [value for value in predicted if value in PREDICTED_RANK]
    if not ranked:
        return NOT_PREDICTED
    return max(ranked, key=PREDICTED_RANK.__getitem__)
