# Defect register — 2026-10-27 (release candidate 2)

Status: FIXED = reproduced by a test, fixed, test passes. OPEN = not fixed. HARDENING = fragile, not a live defect.

## FIXED this release
- **O1 — forecast and reporting-year handling (timeline_analyzer.py).** Reproduced on the previous package: a projection read as a reporting year (2026) and an achieved 2024 value losing its year in a mixed sentence. Fixed with clause-scoped forecast classification, excluding forecast-clause years from reporting-year candidates, anchoring each value to its own position, and keeping a forecast's stated year as target_year. Regression tests: `tests/test_forecast_reporting_year.py` (9). 7 of these fail on the previous code. The earlier attempt was reverted after breaking an achieved result; the final version passes the regression set and changes only the 5 intended sentences in a broad 18-sentence comparison.
- **O2 — "rising to" wording (timeline_analyzer.py).** Forecast only with explicit forward-looking context ("expected to", "on track for", "will", "aims to", "set to", "likely to"). No wall-clock year is used, so results do not depend on run date. A bare "rising to 60%" stays unclassified. Regression tests: `tests/test_rising_forecast_wording.py` (6).
- **H1 — missing scoring_eligible defaulted to eligible (app.py).** Changed `result.get("scoring_eligible", True)` to `result.get("scoring_eligible") is True`. Regression tests: `tests/test_scoring_eligibility_default.py` (4). The source check fails on the previous app.py.
- **N1 — NaN similarity became a match (online_evidence_matcher.py).** NaN compares False to every threshold, so it passed the skip filter and was recorded as a match labelled no_sufficiently_relevant_match. Fixed with a math.isfinite guard before the match is recorded. Regression tests: `tests/test_matcher_nonfinite_scores.py` (3). The filter check fails on the previous code.

## OPEN
- None reproduced in the sandbox that could be fixed without new evidence.

## NOT FIXED, DELIBERATELY (needs real evidence or a decision)
- **Forward-looking wording coverage.** Only the phrases listed above are recognised. Real report language may use other forms ("will be", "targeted to reach"). Extending the list needs real examples and should come with tests for each new phrase.
- **Two-year sentences without forward-looking wording** keep the existing rule: no year is assigned. This is conservative and is retained.
- **Evidence thresholds** (STRONG 0.55, POTENTIAL 0.35) are unchanged. They are documented as retrieval thresholds, not truth thresholds, and must not be lowered to produce matches.

## HARDENING (not live defects)
- **H2.** `web_search.claim_reporting_year` is a second reporting-year implementation (query generation). Not changed. Its tests need ddgs and cannot run here.
- **H3.** `_as_float` in risk_predictor is now None-default (Fix 2). Callers were checked; any future caller must handle None.

## CHECKED, NO DEFECT FOUND
- Source classification: lookalike domains, subdomains and government hosts classified correctly.
- Publication dates never become reporting years.
- Evidence thresholds and match labels: boundaries 0.35 and 0.55 correct.
- Provenance: source_url and original_source_url carried through matches; claim, evidence and source_url carried through NLI results.
- app.py local-import names all defined in their modules (static check).
- Attach-timeline-evidence adds fields only, does not re-derive years.

## NOT VERIFIABLE IN THIS SANDBOX
- Live web search, PDF/HTML collection, real NLI inference, Streamlit UI, SQLite on real data, the Windows validation script (no PowerShell here).
