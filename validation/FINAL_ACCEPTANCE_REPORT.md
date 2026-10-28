# Final acceptance report — ESG Greenwashing Detection System (FINAL)

Built from RC2 (`ESG-Greenwashing-Detection-System-RC2-2026-10-27.zip`), which was verified identical to the working copy before any change.
Environment: Linux sandbox, Python 3.12, **no network**, **no Windows, no PowerShell, no Streamlit, and none of the heavy packages installed.**

## 1. Exact fixes completed this release

| ID | Area | Change | Evidence |
|---|---|---|---|
| O1 | timeline_analyzer.py | Clause-scoped forecast handling; forecast-clause years excluded from reporting-year candidates; each value anchored to its own position; forecast keeps its stated year as target_year | tests/test_forecast_reporting_year.py (9) — 7 fail on the pre-fix code |
| O2 | timeline_analyzer.py | "rising to" is a forecast only with explicit forward-looking context; no wall-clock year used | tests/test_rising_forecast_wording.py (6) |
| H1 | app.py | Missing `scoring_eligible` no longer counts as eligible (`is True`) | tests/test_scoring_eligibility_default.py (4) — source check fails on pre-fix app.py |
| N1 | online_evidence_matcher.py | Non-finite similarity skipped before a match is recorded | tests/test_matcher_nonfinite_scores.py (3) — fails on pre-fix code |
| L1 (new) | timeline_analyzer.py | Internal `_value_position` key leaked into forecast records, changing persisted record_id hashes. Cleanup moved ahead of the Target branch | tests/test_timeline_persistence_keys.py (2) — fails on the leaking version |
| R1 (new) | requirements.txt | `urllib3` imported directly by automatic_collector.py but only available transitively; now declared | static import scan |
| S1 (new) | company_data_builder.py | Module-level file write and prints on import; now under a `main()` guard. Script mode unchanged | import is silent; script mode produces its CSV |
| G1 (new) | app.py | Missing packages produced a raw traceback; now a startup guard lists the missing packages and the install command, exit 1 | `python app.py` in sandbox prints the message and exits 1 |

Earlier fixes retained and verified present: Fix 1 (nli_config), Fix 2 (_as_float None default and unassessed missing NLI/similarity), Fix 3 (reporting-year protection).

## 2. Test results (sandbox, actual runs)

| Run | Condition | Ran | Pass | Assertion failures | Errors (missing package) | Skipped | Exit |
|---|---|---|---|---|---|---|---|
| G | project only, no stubs | 171 | 138 | 0 | 32 | 1 | 1 |
| H | project + labelled stubs (ddgs, pymupdf, plotly) | 206 | 191 | 0 | 14 | 1 | 1 |

Pass = Ran − errors − skipped. Exit 1 is caused only by missing-package errors.
Errors, run G (32): ddgs 21, pymupdf 6, transformers 3, torch 1, and 1 test module that fails on import of plotly (test_risk_visualization). Errors, run H (14): truststore 7, transformers 3, torch 1, and 3 errors from test_offline_workflows / test_company_identity that fail on import (transformers, and the app.py startup guard's SystemExit). The Streamlit AppTest dashboard tests are NOT run in either run: they sit inside test_offline_workflows, which cannot import without transformers.
Logs: `validation/run_G_final_no_deps.log`, `validation/run_H_final_stubs.log`.

Targeted regression run (fixes and affected modules): **72 tests, all OK** (run both before and after the leak fix, and after the startup guard).

## 3. Regression checks

- Timeline: 23 representative sentences compared with the original project. 6 changed; all 6 are intended forecast corrections (future values no longer recorded as achieved results). No correct original output changed.
- Risk heuristic: 162 valid complete rows compared with the original. 0 differences.
- Matcher: classify_similarity keeps finite thresholds (0.55, 0.35) and treats NaN as no match.

## 4. Streamlit

**Not started.** `streamlit` is not installed in this sandbox. The startup guard was verified to report missing packages correctly. The Windows validation script includes an HTTP check; it has not been run.

## 5. Integration tests NOT verified

- Live web search (ddgs), HTML/PDF collection (pymupdf), TLS collection (truststore): blocked; no network.
- Real NLI inference (transformers, torch): blocked; model download needs network.
- The app-shaped round trip (real matcher and NLI feeding review packets): blocked by torch.
- Streamlit UI and AppTest dashboard tests: blocked by streamlit.
- SQLite on the user's real database: not touched, not tested.
- Live tests (test_live_workflows): skipped by design (needs ESG_LIVE_TESTS=1 and internet).
- Windows validation script: not parsed or run in PowerShell.

## 6. Remaining defects that prevent reliable operation

None known that the sandbox can reproduce. The following are unverified, not known defects:
- Any failure in the blocked integration paths above (cannot be ruled out until run on Windows).
- The forecast phrase list is intentionally short; real report wording may need more phrases, each with tests.
- Two-year sentences without forward-looking wording assign no reporting year (conservative, by design).
- `save_predictions` in database.py is a legacy CSV routine not used by the live app; left unchanged.

## 7. Accuracy and scope

The risk score is an experimental deterministic heuristic, not a validated classifier. No accuracy, calibration, or company-level prediction is claimed. There is no independent labelled dataset in the project. No evidence was fabricated and no score was forced. No independent evidence is treated as proof of greenwashing; missing evidence yields an unassessed result.

## 8. Status

Not fully verified. The code changes are tested where the sandbox allows, and the application's real integration paths and Streamlit startup must be verified on Windows using `WINDOWS_VALIDATION.ps1` and the steps in README_WINDOWS.md.
