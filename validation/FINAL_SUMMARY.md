# Final summary — 2026-10-27

- Built from RC2 (verified identical to the working copy).
- Fixed: O1, O2, H1, N1 (carried from RC2, regression-tested), plus L1 (internal key leaking into persisted timeline records), S1 (import-time file write), G1 (clear startup error for missing packages), R1 (declared urllib3).
- Tests (sandbox): 171 run / 138 pass / 0 assertion failures / 32 blocked / 1 skipped without deps; 206 run / 191 pass / 0 assertion failures / 14 blocked / 1 skipped with stubs. Exit 1 only from missing packages.
- Streamlit: NOT started (not installed in the sandbox).
- Not verified here: live collection, PDF/HTML parsing, real NLI inference, Streamlit UI, real database, Windows PowerShell script.
- Next step for the user: run `WINDOWS_VALIDATION.ps1 -InstallDependencies` on Windows and send back SUMMARY.txt.
