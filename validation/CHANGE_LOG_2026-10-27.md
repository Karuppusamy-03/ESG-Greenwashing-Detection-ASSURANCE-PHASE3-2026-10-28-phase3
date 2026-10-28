# Change log — 2026-10-27 (working copy only; original ZIP untouched)

| File | Change | Reason |
|---|---|---|
| nli_config.py | NEW | Dependency-free MODEL_NAME (Fix 1) |
| contradiction_detector.py | MODEL_NAME re-exported from nli_config (line 32) | Fix 1 |
| evaluation/import_review_packet.py | 2 imports -> nli_config | Fix 1 |
| risk_predictor.py | _as_float default None; similarity/NLI missing -> unassessed | Fix 2 |
| timeline_analyzer.py | future "by <year>" values -> Target in _measurement_records | Fix 3 |
| tests/test_review_dependency_isolation.py | NEW (2 tests) | Fix 1 |
| tests/test_risk_missing_values.py | NEW (16 tests) | Fix 2 |
| tests/test_reporting_year_protection.py | NEW (14 tests) | Fix 3 |
| tests/test_offline_workflows.py | 1 assertion block updated (invalid/missing NLI -> NOT_PREDICTED) | Fix 2; module not runnable here |

Backups: validation/backups_2026-10-27/ (contradiction_detector.py, import_review_packet.py, risk_predictor.py, timeline_analyzer.py) and *.pre_fix2 / *.pre_fix3 copies.
Not changed: database schema/logic, app.py, saved-analysis handling, evidence-matching rules, UI, web_search.py.
- 2026-10-27 (run 4): final sandbox runs recorded (run_C, run_D). Added OPEN_DEFECTS, FINAL_STATUS, README_WINDOWS.md, WINDOWS_VALIDATION.ps1 (unparsed, unrun).
- 2026-10-27 (RC2): O1 clause-scoped forecast fix (timeline_analyzer); O2 forward-looking wording; H1 eligibility default (app.py); N1 non-finite similarity guard (online_evidence_matcher). New tests: test_forecast_reporting_year, test_rising_forecast_wording, test_scoring_eligibility_default, test_matcher_nonfinite_scores. Runs E and F recorded. WINDOWS_VALIDATION.ps1 rewritten (unparsed, unrun).
- 2026-10-27 (evidence comparability, on FINAL base): measure labels, material identity, material-content and assurance-scope rules in timeline_analyzer; matcher annotates and demotes incompatible candidates (kept for review); feature_builder excludes them; risk_summary.analysis_risk_category shared by dashboard summary and experimental-prediction line; new tests test_evidence_comparability (15), test_matcher_comparability (7), test_risk_label_consistency (9). Runs E and F recorded. See EVIDENCE_COMPARABILITY_REPORT.md.
- 2026-10-27 (general scope): Apple product names removed from the engine (generic lifecycle rule); homonym logic moved to company_disambiguation.py (config-driven, Apple unchanged over 9 sentences; Shell as second config); company-total and facility patterns widened (scope-number wording, datacenters/campuses/sites); Infosys official domain added; new tests test_cross_company_comparability (15), test_company_disambiguation (7), test_company_configuration (2). Runs E and F recorded. See GENERAL_SCOPE_REPORT.md.
- 2026-10-27 (source integrity): new source_dedupe.py (URL normalisation, content hash, conservative near-duplicates, grouping), extraction_quality.py (USABLE/INCOMPLETE/MALFORMED, text unchanged), assurance_classifier.py (standalone, not yet wired). online_evidence_matcher: quality before gate, duplicate-aware independent support, new status candidates_found_low_quality_extraction. feature_builder excludes duplicates and malformed text. tests/test_source_integrity.py (29). Runs E and F recorded. See INTEGRITY_WORKSTREAMS_REPORT.md.
