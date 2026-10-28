# Baseline audit — ESG Greenwashing Detection System

Date: 2026-10-27
Source: `ESG-Greenwashing-Detection-System-main.zip` (uploaded snapshot), extracted to a separate working copy. The original archive was not modified.
Environment: Linux sandbox, Python 3.12.3, **no network access**, pip could not install packages.

## 1. Snapshot identity

- No `.git` directory is present in the ZIP. The snapshot **cannot be matched to a GitHub commit or branch**. Uncommitted changes on the user's machine cannot be ruled out.
- 64 files, ~1.2 MB, ~27,600 lines of Python across root, `evaluation/`, `tests/`, `local_checks/`.
- `.gitignore` excludes `data/` and `output/`. **No `data/greenwashing_risk.db`, no saved analyses, and no collected documents are in the ZIP.** The only analysis JSON is `tests/fixtures/saved_analysis_synthetic.json`, which is marked synthetic (fictional "Example Corp", `.test` domains).
- `verify_project.ps1` is **0 bytes (empty)**.
- Redundant copies of the app exist: `app_backup.py`, `app_before_product_removal.py`. These are not imported by the test suite; they should not be modified or deleted without the user's decision.

## 2. Dependencies

`requirements.txt` lists: streamlit, pandas, numpy, scikit-learn, xgboost, shap, transformers, sentence-transformers, torch, pymupdf, plotly, ddgs, requests, truststore, beautifulsoup4, matplotlib.

Installed in the sandbox: pandas, numpy, scikit-learn, requests, beautifulsoup4, matplotlib.
**Missing:** pytest, streamlit, xgboost, shap, transformers, torch, pymupdf, plotly, ddgs, truststore.
Installation was impossible (no network). This is an environment limitation, not a project defect.

## 3. Test results (actual runs)

pytest is not installed, so the suite was run with the standard library runner:

    PYTHONPATH=.:tests python3 -m unittest discover -s tests -p "test_*.py" -t tests

**Result: Ran 115 tests — 33 errors, 1 skipped, 0 assertion failures.** (Log: `validation/baseline_unittest.log`.)

Breakdown of the 33 errors, all caused by missing packages (none is a logic assertion failure):

| Cause | Count | Affected modules |
|---|---|---|
| `ddgs` missing | 21 | `test_web_search` (WebSearchTests) and imports in `test_company_identity`, `test_query_year_selection` |
| `pymupdf` missing | 6 | `test_collector_tls` and related collector tests |
| `transformers` missing | 4 | `test_nli_unavailable_scoring`, `test_offline_workflows`, `test_risk_heuristics` |
| `torch` missing | 1 | `test_pair_review::ProducerConsumerIntegrationTests` |
| `plotly` missing | 1 | `test_risk_visualization` |

Note: `test_review_workflow::test_imports_adjudicated_nli_labels_with_saved_outputs` fails at `evaluation/import_review_packet.py:126`, which imports `contradiction_detector`, which imports `transformers`. **The human-review import path therefore requires the full NLI stack even when no model is run.** This is a real coupling defect, not just a sandbox limitation: the review tooling cannot be tested in a lightweight environment.

Seven test modules failed at import time, so their tests never ran. Their counts are not included above.

**Not verified in this sandbox:** every test that depends on `ddgs`, `pymupdf`, `transformers`, `torch`, or `plotly`. These must be run on the user's Windows machine with `requirements.txt` installed.

## 4. Compile check

`python3 -m compileall -q .` → exit 0. All Python files compile. This does not prove they import or run.

## 5. Streamlit app

Not started. Streamlit is not installed. The app's startup **has not been verified** in any environment.

## 6. Verified claims in existing documentation

I checked the claims in `PIPELINE_VALIDATION_REPORT.md` and `COMPLETION_MATRIX.md` against the code:

- **D1 (failed NLI counted as completed zero-count):** Fix is present. `contradiction_detector.py` (~lines 360–374) sets `scoring_eligible = category != "UNAVAILABLE"` and `nli_failed`. `feature_builder.py` (lines 9–12, 88) excludes unavailable results from completed counts. **Code-level verified. Not re-run through tests** (the D1 test module needs `transformers`).
- **D2 (partial NLI coverage scored as complete):** Fix is present. `feature_builder.py` emits `nli_pairs_eligible`, `nli_pairs_completed`, `nli_coverage_complete` (lines 100–134). `risk_predictor.py` (lines 42, 64–98, 176–180) returns `None` / `NLI_PARTIAL_REASON`. **Code-level verified; tests not run.**
- The docs state that company-level ground truth is **not available** (`RESEARCH_QUALITY_AUDIT.md:62`). Confirmed.
- The docs state that reviewer labels are not validated against external ground truth (`KNOWN_LIMITATIONS.md:44`). Confirmed.

## 7. Human-review and evaluation data status

- `evaluation/nli_annotation_template.csv` — **header only, 0 data rows.**
- `evaluation/risk_annotation_template.csv` — **header only, 0 data rows.**
- `evaluation/risk_labels.csv` — **does not exist.** `evaluate.py` expects it and raises `FileNotFoundError` by design ("No labeled evaluation was run").
- No `final_labels.csv`, consensus file, adjudication file, or reconciled output exists in the ZIP.
- No reviewer identifiers, reviewer labels, or adjudicator records exist anywhere in the snapshot.
- **Conclusion: zero genuine human labels, zero adjudications, and zero company-level ground truth are present.** None was fabricated during this audit.

## 8. Pipeline review (code inspection)

- `contradiction_detector.py`: `normalize_label` maps unrecognized outputs to `UNKNOWN` and then to `UNAVAILABLE`, so malformed NLI output is not silently treated as a contradiction. Good.
- `risk_predictor.py::_heuristic_risk_score` returns `None` for missing evidence, unavailable NLI, and partial coverage. Good.
- **Latent smell (not a live defect):** `risk_predictor._as_float` defaults missing NLI counts and similarity to `0.0`. The guards above return `None` before those counts are used, so a missing count cannot reach the score today. Recommend making the default explicit (`None`) so future edits cannot reintroduce a silent zero.
- `timeline_analyzer.py`: `reporting_year` is derived from sentence-level year matches and is `None` for target statements. I found **no fallback that uses `publication_date` as the reporting year** (`publication_date` is only passed through at line 757). Good, but covered by no regression test I could identify.
- Review tooling: `evaluation/pair_review.py` (772 lines) and `import_review_packet.py` (257 lines) implement blinded packets, validation, reconciliation, and finalization. Their blinding and tamper-check logic could not be exercised here because of the `torch`/`transformers` import coupling.

## 9. Earliest blockers identified for the real pipeline

The real pipeline cannot be exercised in this sandbox, so these are blockers from code and data inspection, not from a live run:

1. **No saved analyses or database in the snapshot.** Pipeline tracing on real companies requires the user's `data/` folder, which is gitignored and was not uploaded.
2. **Live collection requires network access** (`ddgs` web search, HTTP fetches). Not possible here.
3. **NLI requires `transformers` and a model download** (`contradiction_detector.py` loads the classifier lazily). Not possible here.
4. **Review-import path depends on the NLI stack** (`import_review_packet._nli_predictions` imports `contradiction_detector`). Recommend moving `MODEL_NAME` into a dependency-free module so the review workflow can be tested without `torch`.

## 10. Items requiring the user's machine or genuine human input

- Run the full suite with `requirements.txt` installed on Windows (`run_all_tests.ps1` or `python -m unittest discover -s tests -v`).
- Provide `data\greenwashing_risk.db` and saved analyses (or confirm they should not leave the machine).
- Provide genuine reviewer labels from two independent people and an adjudicator. None exist.
- Provide or identify an independent company-level ground-truth dataset, with provenance, if one exists. None exists in the project.

---

## 11. Changes made in this working copy (2026-10-27)

Original ZIP unchanged (SHA-256 prefix `eca5acbc8f033668`). Pre-edit backups in `validation/backups_2026-10-27/`.

### Fix 1 — Review workflow no longer loads the NLI stack

Cause: `evaluation/import_review_packet.py` imported `MODEL_NAME` from `contradiction_detector`, which imports `transformers` at module top. The review path therefore required `transformers` even when no model ran.

Changes:
- NEW `nli_config.py`: dependency-free `MODEL_NAME` constant (identical string).
- `contradiction_detector.py`: `MODEL_NAME` now re-exported from `nli_config`. Existing `contradiction_detector.MODEL_NAME` references and behaviour are unchanged.
- `evaluation/import_review_packet.py`: 2 imports redirected to `nli_config`.
- NEW `tests/test_review_dependency_isolation.py`: runs each review module in a subprocess with ML packages blocked.

Observed:
- Review modules import with torch/transformers/xgboost/shap/ddgs/fitz/plotly blocked: **OK** for `nli_config`, `evaluation.prepare_review_packet`, `evaluation.pair_review`, `evaluation.import_review_packet`, `evaluation.evaluate`, `evaluation.evaluate_nli`.
- `tests.test_review_dependency_isolation`: **2 passed**.
- `tests.test_review_workflow`: **6 passed** (previously 1 error from the `transformers` import).

### Fix 2 — Missing NLI/similarity no longer read as zero

Cause (verified by probe): `risk_predictor._as_float` defaulted to `0.0`. Two real paths could turn missing data into a numeric score:
1. Missing or invalid `similarity` scored as 0.0 (probe: a row with NaN similarity scored **25.0**). `feature_builder` produces `similarity=None` when no similarity exists, so this path is reachable.
2. A single missing NLI count next to present counts was read as zero (probe: scored **10.0**).

Changes (`risk_predictor.py`, backup `risk_predictor.py.pre_fix2`):
- `_as_float` default changed from `0.0` to `None`, with a docstring. Only the default changed.
- `_heuristic_risk_score`: returns unassessed (`None`) when similarity is missing or invalid, and when any NLI count is missing. Genuine zero counts still score.

Callers checked: `_as_float` is called only inside `_heuristic_risk_score`. No other caller exists in the repository.

Observed:
- Equivalence check, original vs fixed, over **162 valid complete combinations** (similarity × NLI counts): **0 differences**. Valid scoring is preserved.
- New `tests/test_risk_missing_values.py`: **16 passed** on the fixed code; **18 failures** on the original code (the regression is proven).
- `tests.test_risk_unavailable_states`: **12 passed** (unchanged behaviour).

### Fix 3 — Reporting-year protection in timeline extraction

Cause (verified by probe and comparison): `timeline_analyzer._measurement_records` classed a value as a *Target* only when a target keyword (e.g. "target", "aim", "commit") was present. A future value attached to "by <future year>" with no keyword was recorded as a **reported result for the sentence's real year**. Example: "We cut Scope 1 emissions to 800 t in 2024, on track for 500 t by 2030" recorded the **500 t forecast as a 2024 actual**.

Changes (`timeline_analyzer.py`, backup `timeline_analyzer.py.pre_fix3`):
- In `_measurement_records`: a value in the same clause as, and before, a `by <year>` marker is a Target when that year is strictly later than every explicit reporting year in the sentence. Clause-scoped, so the 2024 actual is not affected.
- Comparison original vs fixed over 14 sentences: 3 changed, all intended (future values reclassified from "reported for year X" to "target for year Y"). The remaining 11, including achieved, baseline and pure-reporting cases, are unchanged.

Observed:
- New `tests/test_reporting_year_protection.py`: **14 passed** on the fixed code; **3 failures** on the original code (the three forecast misattributions).
- Existing possessive-baseline assertion (`test_offline_workflows.py:2112`) verified directly: **passes**.

Test correction (not a code change): a new test expected two reporting years in one sentence to yield two years. The existing, deliberate behaviour (`_explicit_reporting_years` returns `None` when several reporting years exist, to avoid guessing) is pinned instead. Verified identical on original and fixed code.

### Existing test updated for Fix 2

`tests/test_offline_workflows.py` (~line 2012): an assertion expected an invalid-similarity, missing-NLI row to receive a numeric score in [0, 100]. That expectation encoded the zero-fill behaviour Fix 2 removes. It now asserts the row is unassessed (`NOT_PREDICTED`, NA score, NA probability). Its assertion logic was verified directly. **This module cannot be imported in the sandbox (needs `transformers`), so the updated test itself has not been executed by the test runner.**

## 12. Test results after the changes (sandbox, unittest runner, no pytest)

Command: `PYTHONPATH=.:tests python3 -m unittest discover -s tests -p "test_*.py" -t tests`

- Before: Ran 115, errors 33, skipped 1, assertion failures 0.
- After: **Ran 147, errors 32, skipped 1, assertion failures 0.**
- Errors removed: 1 (`test_review_workflow` import, Fix 1).
- Errors added: **0.**
- Remaining 32 errors are all `ModuleNotFoundError` for `ddgs` (21), `pymupdf` (6), `transformers` (3), `torch` (1), `plotly` (1). Each is an environment limit.

Blocked in this sandbox (not run, not claimed as passing): `test_risk_heuristics`, `test_nli_unavailable_scoring`, `test_offline_workflows` (contains the updated Fix 2 assertion), `test_web_search`, `test_company_identity`, `test_query_year_selection`, `test_collector_tls`, `test_risk_visualization`, `test_pair_review::ProducerConsumerIntegrationTests`.

## 13. Known limitations of these fixes

- Fix 3 is a narrow rule. It handles "value followed by a future `by <year>`" in the same clause. It does not resolve sentences with two reporting years (deliberately left unassigned) or other target phrasings. This is documented, not claimed as complete.
- Fix 3 only corrects the timeline path. `web_search.claim_reporting_year` is a separate implementation (query generation) that already excludes target years and was not changed. It could not be executed here because `ddgs` is missing.
- All evidence above is synthetic-input and software-logic verification. None of it measures real-world detection accuracy.

## 14. Final sandbox run (after all three fixes)

Command: `PYTHONPATH=.:tests python3 -m unittest discover -s tests -p "test_*.py" -t tests` (log: `validation/final_unittest.log`).
Observed: see the final line of the log. Assertion failures and errors are reported there and in section 12.
These results are sandbox results only. They are not Windows results, and they do not show that the Streamlit app runs.
