"""Honest outcome summary for the NLI stage (pure function, no model needed).

Every record in analysis["nli_results"] falls into exactly one outcome:

  evaluated            - classified by NLI and scoring_eligible is True
  excluded_duplicate   - copy of evidence already in the batch; never sent to the model
  excluded_quality     - malformed extraction; never sent to the model
  gate_skipped         - stopped by the similarity, entity or comparability gates
  model_failed         - model error, timeout or unrecognised output; UNAVAILABLE, not a contradiction

"Eligible" candidates are all records minus the two excluded kinds. Stage status uses the
existing vocabulary: COMPLETED, PARTIAL, FAILED, NOT AVAILABLE.
"""

from __future__ import annotations

CLASSIFIED = {"ENTAILMENT", "CONTRADICTION", "NEUTRAL"}
EXCLUDED_DUPLICATE = "DUPLICATE_COPY"
EXCLUDED_QUALITY = "MALFORMED_EXTRACTION"


def summarize_nli_outcomes(records):
    records = [record for record in (records or []) if isinstance(record, dict)]
    total = len(records)
    excluded_duplicate = sum(1 for r in records if r.get("compatibility_status") == EXCLUDED_DUPLICATE)
    excluded_quality = sum(1 for r in records if r.get("compatibility_status") == EXCLUDED_QUALITY)
    eligible = total - excluded_duplicate - excluded_quality

    evaluated_records = [
        r for r in records
        if r.get("nli_result") in CLASSIFIED and r.get("scoring_eligible") is True
    ]
    evaluated = len(evaluated_records)
    model_failed = sum(1 for r in records if r.get("nli_failed") is True)
    gate_skipped = sum(
        1 for r in records
        if r.get("nli_result") == "UNAVAILABLE"
        and r.get("nli_failed") is not True
        and r.get("compatibility_status") in {"INCONCLUSIVE", "INCOMPATIBLE"}
    )
    potentially_related_evaluated = sum(
        1 for r in evaluated_records if r.get("source_relation") == "potentially_related"
    )

    counts = {
        "total_records": total,
        "eligible_candidates": eligible,
        "evaluated": evaluated,
        "excluded_duplicate": excluded_duplicate,
        "excluded_quality": excluded_quality,
        "gate_skipped": gate_skipped,
        "model_failed": model_failed,
        "potentially_related_evaluated": potentially_related_evaluated,
    }

    exclusion_note = ""
    if excluded_duplicate or excluded_quality:
        exclusion_note = (
            f" {excluded_duplicate} duplicate copies and {excluded_quality} malformed "
            "statements were excluded before NLI and were not evaluated."
        )

    if total == 0:
        status = "NOT AVAILABLE"
        message = "NLI requires at least one matched evidence pair."
    elif eligible == 0:
        status = "NOT AVAILABLE"
        message = (
            "No eligible evidence pairs for NLI evaluation: every matched candidate was a "
            f"duplicate copy or malformed text ({excluded_duplicate} duplicate, "
            f"{excluded_quality} malformed), and none was sent to the model."
        )
    elif evaluated == eligible:
        status = "COMPLETED"
        message = f"All {evaluated} eligible evidence pair(s) were evaluated by NLI." + exclusion_note
    elif evaluated == 0 and model_failed > 0:
        status = "FAILED"
        message = (
            "The NLI model returned no usable result for any eligible pair. No pair was "
            "classified as support or contradiction." + exclusion_note
        )
    elif evaluated == 0:
        status = "PARTIAL"
        message = (
            f"No eligible pair was evaluated: {gate_skipped} of {eligible} were skipped by the "
            "similarity, entity or comparability gates. These pairs are "
            "unavailable or ineligible for support/contradiction scoring."
            + exclusion_note
        )
    else:
        status = "PARTIAL"
        message = (
            f"{evaluated} of {eligible} eligible evidence pair(s) were evaluated; "
            f"{gate_skipped} skipped by gates and {model_failed} failed in the model."
            + exclusion_note
        )

    return {"status": status, "message": message, "counts": counts}
