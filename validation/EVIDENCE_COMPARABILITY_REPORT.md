# Evidence comparability, source independence and risk-label consistency — report

Date: 2026-10-27. Environment: Linux sandbox, Python 3.12, **no network**, **no Windows**, **no Streamlit**, and the real NLP/PDF/web packages are **not installed**. Every result below is from unit-level or synthetic tests unless marked otherwise.

## 0. Important: which code line this work is on
The uploaded `ESG-Greenwashing-Detection-System-main__1_.zip` predates the RC2/FINAL fixes (O1, O2, H1, N1, Fix 1–3, startup guard). None of those fixes or their tests are in the upload. To avoid silently losing them, this work was applied to the **FINAL line** (`ESG-Greenwashing-Detection-System-FINAL.zip`, verified to contain them), not to the upload. The upload itself was not modified. If your Windows copy is the upload rather than FINAL, these changes must not be merged onto it without first restoring the earlier fixes.

Baseline on the FINAL line before this work: 171 tests, 0 assertion failures, 32 missing-package errors, 1 skip.

## 1. Root causes (diagnosed in the code before any change)
1. **The matcher ranked by similarity only.** `online_evidence_matcher.match_online_evidence` labelled any candidate above 0.35 as `potentially_relevant` and never consulted the existing comparability gate (`compare_measurement_compatibility`).
2. **The metric vocabulary is too coarse.** Avoided emissions and supplier-program figures are stored as `absolute_emissions`, the same key as a company's gross total. Product footprints share `emissions_reduction_percent` with company-wide reductions. Rare-earth, recycled-material and facility-coverage claims produce no usable measure at all. The gate can only reject pairs whose keys differ.
3. **The gate reported the wrong reason.** Real measure mismatches surfaced as a modality mismatch or as "missing metadata", i.e. `INCONCLUSIVE`, not `INCOMPATIBLE`.
4. **The assurance-scope check did not check scope.** It handled baseline-year and target exclusions only; a claim covering Scopes 1 and 3 was not blocked by an assurance that excludes Scopes 1 and 3.
5. **Incompatible candidates could still score.** `feature_builder` excluded only `weak_match` and `no_sufficiently_relevant_match`, so a new `incompatible_candidate` label would have leaked into scoring. This was reproduced by a test before it was fixed.
6. **Two different analysis-level risk rules.** The dashboard summary used the first predicted row; the "Experimental risk prediction" line used the maximum across rows. The same analysis could show MEDIUM in one place and HIGH in another, depending on row order.
7. **A crash in my own first port.** The gate call assumed dict claims; the pipeline passes plain strings. This would have failed on every candidate. It was caught by running production-shaped input and fixed; tests now use the string shape.

## 2. Changes (files and purpose)
| File | Change | Why |
|---|---|---|
| `timeline_analyzer.py` | Added `measure_labels` (avoided/supplier, product footprint, facility coverage, company gross total), `material_of`, `MATERIAL_CONTENT_PATTERN`. The gate now returns `INCOMPATIBLE` when named measures differ, when a material-content claim is checked against emissions/energy evidence or a different material, when a claim covers all facilities but evidence covers a subset, and when a claim covers a scope the assurance explicitly excludes. | Causes 2, 3, 4 |
| `online_evidence_matcher.py` | Optional injected `cos_sim` (default unchanged). Each candidate is annotated with `comparability_status` and `comparability_reason`; an incompatible candidate gets `match_label = incompatible_candidate` and is **kept** for review. Claim status becomes `candidates_found_but_incompatible` when every candidate is incompatible. Accepts string or dict claims. | Causes 1, 7 |
| `feature_builder.py` | Comparability-rejected candidates never count as scoring evidence (`INCOMPATIBLE` status and `incompatible_candidate` label both excluded). | Cause 5 |
| `risk_summary.py` (new) | One pure function, `analysis_risk_category`: highest category among predicted rows; `NOT_PREDICTED` if none. | Cause 6 |
| `app.py` | Replaced the first-row summary and the local maximum with `analysis_risk_category`. The dashboard still shows "Unavailable" when nothing was predicted (original text kept). Row-level table unchanged. | Cause 6 |
| `tests/test_evidence_comparability.py` (new) | 15 tests: Apple scenarios A–E, facility coverage, assurance scope, material identity. | Regression |
| `tests/test_matcher_comparability.py` (new) | 7 tests: candidates kept with source link, incompatible is not "potentially relevant", feature exclusion, string-claim shape, scenarios B and E at matcher level. | Regression |
| `tests/test_risk_label_consistency.py` (new) | 9 tests: order independence, NOT_PREDICTED, unknown values, app uses one rule, "Unavailable" text kept. | Regression |

No schema change. No database change. No threshold change (0.55 strong, 0.35 weak unchanged). The `metric_key` vocabulary is unchanged because it is persisted; the distinction is carried by the measure label instead.

## 3. Test changes (disclosed)
- `test_evidence_comparability` assertions were strengthened from "not COMPATIBLE" to the specific expected status (`INCOMPATIBLE`) and the documented reason. The earlier weaker assertion had passed while the gate returned the wrong reason, so it did not detect the defect.
- One assertion changed from checking the internal `metric_key` to checking the measure label, because the persisted key vocabulary was deliberately not changed.
- No assertion was removed. No test was skipped.

## 4. Test results (sandbox; logs in `validation/`)
| Run | Ran | Passed | Failures | Errors (missing package) | Skipped | Exit |
|---|---|---|---|---|---|---|
| E, no optional packages | 202 | 169 | 0 | 32 | 1 | 1 |
| F, with labelled stubs for ddgs/pymupdf/plotly | 237 | 222 | 0 | 14 | 1 | 1 |

Baseline (FINAL line): 171 ran / 0 failures / 32 errors / 1 skip (no stubs). Change: +31 tests, no new errors, no removed errors. Error set compared line by line with the baseline: identical except for the new tests. Exit 1 is caused only by the missing-package errors.

**Not executed here:** `test_offline_workflows`, `test_risk_heuristics`, `test_nli_unavailable_scoring`, `test_web_search`, `test_company_identity`, `test_query_year_selection` need `transformers`, `ddgs` or `truststore`. I reproduced their matcher fixtures by hand against the ported matcher (`fixture 1` and `fixture 2` in the session; `test_risk_heuristics` fixture): the expected labels and statuses are unchanged (`potentially_relevant_evidence_found`, `COMPATIBLE` or `NOT_QUANTITATIVE`). These modules must still be run on Windows.

Compile check excluding `.venv`: exit 0. No stray control characters in edited files. Byte-order marks preserved.

## 5. Apple scenarios — before and after
**Important:** I could not fetch Apple's sources or run a live analysis (no network), and no Apple saved analysis was in the upload. The table uses **synthetic sentences with the same structure as each Apple claim type**. It shows how the matcher treats each *type of pair*. It is **not** evidence about Apple.

| Case | Claim type | Evidence type (synthetic) | Before (FINAL matcher) | After |
|---|---|---|---|---|
| A | Gross Scope 1–3 reduction vs baseline | Supplier avoided emissions | potentially_relevant_evidence_found | candidates_found_but_incompatible (INCOMPATIBLE: company gross total vs avoided/supplier) |
| B | 99% recycled rare-earth magnets | Total Scope 3 emissions fell | potentially_relevant_evidence_found | candidates_found_but_incompatible (INCOMPATIBLE: material vs emissions) |
| C | Mac mini footprint −80% vs BAU | Company-wide Scope 3 fell | potentially_relevant_evidence_found | candidates_found_but_incompatible (INCOMPATIBLE: product footprint vs company gross total) |
| D | All own facilities renewable since 2018 | Supplier clean-energy generation | potentially_relevant_evidence_found | candidates_found_but_incompatible (INCOMPATIBLE: facility coverage vs supplier program) |
| E | Increased recycled materials across products | Total emissions across operations | potentially_relevant_evidence_found | candidates_found_but_incompatible (INCOMPATIBLE: material vs emissions) |

Per the brief, the honest status for each Apple case **with real sources** is "insufficient comparable evidence found" unless a real comparable source is retrieved. This work demonstrates only that incompatible pairs are no longer presented as support. It does not show that comparable Apple evidence exists.

## 6. Not implemented in this session (honest gaps)
- **Live Apple collection and a fresh analysis** — blocked (no network). Before/after counts for real claims, sources and records are **not available**.
- **Duplicate and repeated-source handling (brief test 10)** — not changed. The matcher dedupes by URL and text only, so the same report at two URLs can still count twice.
- **Noisy PDF / table-fragment handling (brief test 11)** — not changed.
- **Reviewer and assurance independence (brief §5)** — only the assurance-scope exclusion was added. Reviewer-versus-publisher-versus-author distinctions are not modelled beyond existing fields.
- **Metric vocabulary** — avoided, product and material measures are carried as labels, not as persisted metric keys. Changing the persisted vocabulary would need a migration decision.
- **Evidence-category labels for INCONCLUSIVE pairs** — an `INCONCLUSIVE` candidate can still show as `potentially_relevant`. The brief's "potentially relevant, incomplete" category exists in principle but is not separated in the UI.
- **Risk outputs** — the label-consistency fix covers the three analysis-level displays. The row-level table, the saved JSON, and any Streamlit rendering were not run.
- **Streamlit and browser UI** — not started. Not verified.

## 7. Preservation
- No database, schema, saved-analysis or collected-document file was touched. The sandbox contains none of your data.
- Upload not modified. Work done in a separate copy of the FINAL line.
- No thresholds lowered. No evidence or scores fabricated. Missing or incompatible evidence is never treated as proof of greenwashing.
