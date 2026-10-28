# Test validation report — 2026-10-27 (sandbox, working copy)

Scope: current working copy after Fixes 1–3. Original ZIP unchanged.
Environment: Linux sandbox, Python 3.12.3, **no network** (PyPI unresolvable; `pip download` returns no versions). Nothing could be installed.
These are sandbox results. They are not Windows results, and they do not show that the Streamlit app runs.

## 1. Result counts

| Run | Condition | Ran | Passed | Failed (assertion) | Errors (blocked by missing package) | Skipped |
|---|---|---|---|---|---|---|
| A | Project only, no stubs | 147 | 114 | **0** | 32 | 1 |
| B | Project + sandbox stubs (ddgs, pymupdf, plotly) | 182 | 167 | **0** | 14 | 1 |

"Passed" = Ran − errors − skipped. Exit code for both runs: **1** (non-zero because of errors that come from missing packages, not from assertions).

## 2. Blocked tests, by missing package

Run A (no stubs), 32 errors:
- `ddgs` — 21 (test_web_search; test_company_identity; test_query_year_selection)
- `pymupdf` — 6 (test_web_search collection tests; test_collector_tls)
- `transformers` — 3 (test_offline_workflows; test_risk_heuristics; test_nli_unavailable_scoring)
- `torch` — 1 (test_pair_review::test_app_shaped_analysis_round_trips_into_packets)
- `plotly` — 1 (test_risk_visualization)

Run B (with stubs), 14 errors:
- `truststore` — 7 (test_web_search collection tests; test_collector_tls)
- `streamlit` — 3 (test_offline_workflows dashboard `AppTest` tests)
- `transformers` — 3
- `torch` — 1

Stubs cannot safely cover `truststore` (controls TLS in automatic_collector; faking it would give a false pass to test_collector_tls), `streamlit` (needed for the real AppTest dashboard tests), `torch`/`transformers` (would invent NLI behavior). These stay blocked until Windows.

## 3. Skipped test (1)

`tests/test_live_workflows.py::LiveWorkflowTests::test_company_web_workflow`. Skipped by design: requires `ESG_LIVE_TESTS=1` and live internet. Run on Windows with that variable set.

## 4. Genuine assertion failures

**0** in both runs. No unexpected exceptions other than missing-package imports.

## 5. Test expectations changed in this session

Two existing expectations in `tests/test_offline_workflows.py` were changed. Both encoded the old zero-fill behaviour that Fix 2 removes, and both conflicted with documented intent:

1. Invalid-similarity / missing-NLI row: expected a numeric risk score in [0, 100]. Now expects unassessed (`NOT_PREDICTED`, NA score, NA probability). Documented intent: missing NLI/similarity is unassessed (`risk_predictor.py`, `test_risk_unavailable_states`).
2. Same row: `explain_risk_predictions(...)` expected a non-empty list. Now expects `[]`. Documented intent: the explainer returns `[]` for unassessed rows (`test_risk_unavailable_states::test_explainer_with_only_unassessed_rows_returns_empty`).

Backup before change: `validation/backups_2026-10-27/test_offline_workflows.py.pre_run3`.

**Status of these two changed assertions: not executed by the runner.** The module needs `transformers`. I verified the same assertion logic directly (see section 6). They must be confirmed on Windows.

## 6. Verification of blocked-module assertions by direct execution

These assertions sit in modules that cannot import here. Their logic was run directly, without changing the test files:

- Fix 2 assertions (both changed expectations above): **5/5 pass** (risk_score NA, status NOT_PREDICTED, probability all NA, category NOT_PREDICTED, explanations == []).
- `test_timeline_uses_explicit_years_and_withholds_missing_years`: **pass** (reported years [2021, 2022]; change text "decreased by 20").
- `test_timeline_separates_reported_measurement_from_target_year`: **pass** (40% Reported 2024; 100% Target 2030).
- `test_timeline_does_not_treat_possessive_baseline_as_reporting_year`: **pass** (baseline-only gives no records; 2024 measurement gives one 2024 record).

Direct execution is a check of the same logic. It is not a runner result.

## 7. The three recent fixes, verified by the runner

| Module | Ran | Result |
|---|---|---|
| test_review_dependency_isolation (Fix 1) | 2 | OK |
| test_review_workflow (Fix 1) | 6 | OK |
| test_risk_missing_values (Fix 2) | 16 | OK |
| test_risk_unavailable_states (Fix 2) | 12 | OK |
| test_reporting_year_protection (Fix 3) | 14 | OK |

Total for the fix-related modules: **50 passed, 0 failed.**

Fix 2 regression tests fail on the original code (18 assertion failures). Fix 3 regression tests fail on the original code (3 assertion failures). See BASELINE_AUDIT section 11.

## 8. Compile check

`python3 -m compileall -q .` → **exit 0**. Log: `validation/compile.log`.

## 9. Streamlit startup

**Not run.** `streamlit` is not installed, so `streamlit run app.py` cannot start here. The "exit=0" printed in the earlier shell output came from `tail`, not from Python; it does not represent a successful import. Treat Streamlit as **unverified**.

## 10. Limitations

- Stubs are used only in Run B, and only to let the logic of mocked tests execute. Run B results are "logic executed against stubbed packages." They are not a validation of ddgs, pymupdf, or plotly behaviour.
- No test in either run measures real-world detection accuracy. All use synthetic or mocked inputs.
- No dependency versions are pinned in requirements.txt (except truststore). Windows installs will use whatever current versions pip resolves; record them with `pip freeze`.

## 11. Overall status

- Completed and verified in sandbox: compile check; the five fix-related modules (50 tests); direct execution of blocked-module assertions.
- Blocked by environment (needs Windows): 32 tests in Run A, 14 in Run B; Streamlit startup; the skipped live test.
- Actual failures: none found.
- The suite is **not** claimed to pass. It has not been run to completion in an environment with its dependencies installed.
