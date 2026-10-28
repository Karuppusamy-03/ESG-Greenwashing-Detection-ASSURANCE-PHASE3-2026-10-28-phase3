# Final status — release candidate 2 (2026-10-27, sandbox)

## Test results (sandbox; exit codes recorded)
| Run | Condition | Ran | Assertion failures | Blocked (missing package) | Skipped | Exit |
|---|---|---|---|---|---|---|
| E | project only, no stubs | 169 | 0 | 32 | 1 | 1 |
| F | project + labelled stubs (ddgs, pymupdf, plotly) | 204 | 0 | 14 | 1 | 1 |

Exit 1 in both runs is caused by missing-package errors, not by assertion failures. Logs: `run_E_no_deps.log`, `run_F_stubs.log`.

- New and fix-related modules (72 tests): **OK**, all pass.
- Error set compared with the previous release: no new errors, no removed errors.
- Compile check of all 29 edited files: pass; no misplaced BOMs.
- Skipped: `test_live_workflows` (needs ESG_LIVE_TESTS=1 and internet).

## Not verified in this sandbox
- Streamlit startup: `streamlit` is not installed. Not run.
- The 32 (or 14) dependency-blocked tests: not executed.
- Live web collection, PDF/HTML parsing, real NLI inference, SQLite on real data.
- `WINDOWS_VALIDATION.ps1`: PowerShell is not available here, so the script has **not been parsed or run**. Brace and parenthesis counts balance, which is not a substitute for parsing.

## Defects
- Fixed and tested: O1, O2, H1, N1 (see OPEN_DEFECTS_2026-10-27.md).
- Open: none that could be safely fixed in this sandbox.

## Accuracy
- The risk score is an experimental deterministic heuristic, not a validated classifier.
- No accuracy, calibration, or company-level predictive performance is claimed. No independent labelled dataset exists in the project.

## Status
Not complete. Dependency-blocked tests, Streamlit startup, live collection, and the Windows script still need a real run on Windows. See WINDOWS_TEST_RUN_COMMANDS.md and README_WINDOWS.md.
