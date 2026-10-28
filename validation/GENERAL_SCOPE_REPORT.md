# General-scope report: company-independent comparability (2026-10-27)

## 0. Scope and honesty
- Environment: Linux sandbox, **no network, no Windows, no Streamlit, real NLP/PDF/web packages not installed**. Results below are unit-level and synthetic.
- **No live evidence was retrieved for any company.** No Apple, Samsung, Microsoft, Tesla or Infosys source was fetched. Every "pair" is a synthetic sentence written to match a claim structure. These tests check gate behaviour, not real-world accuracy.
- **No reviewed labelled dataset exists in the project.** Precision and recall against human labels are therefore **not measured**. Prediction accuracy is unvalidated.
- Base: the FINAL-line package (the uploaded snapshot predates the earlier fixes and was not used as the base).

## 1. Root causes found in the code
1. **Apple-specific product names in the general engine.** `timeline_analyzer.py` listed Mac, iPhone, iPad, Apple Watch, etc. in the product-footprint rule. **Fixed:** replaced by a generic lifecycle/product pattern (checked on Galaxy S24, Xbox Series X and Mac mini wording).
2. **Apple-only homonym logic in the collector.** `web_search.py` had Apple-specific food-disambiguation terms hard-coded. **Fixed:** moved to `company_disambiguation.py`, driven by per-company configuration. The Apple function now delegates. Old and new behaviour compared over 9 sentences: **0 differences**. A second configured company (Shell) exercises the same code path.
3. **Company-total pattern missed "gross Scope 1 and 2 emissions".** Only adjacent wording matched. **Fixed**: scope-number wording now recognised. Checked for false positives ("gross margin" is not labelled).
4. **Facility pattern missed datacenters, campuses, sites, plants, stores, offices.** **Fixed**; the all-versus-subset check uses the same nouns.
5. **Official-domain configuration missing for Infosys.** **Fixed** (`infosys.com`). Tesla, Samsung, Microsoft and Apple were already configured.

## 2. Deliberately not changed
- **Modality classifier.** Two statements with no explicit reporting language (for example "decreased by 40% … in its 2023 sustainability report") stay `unspecified` and return `INCONCLUSIVE`. An existing test (`test_unspecified_measurement_status_is_inconclusive`) pins this conservative rule, so it was not loosened. Compatible pairs in the tests therefore use explicit reporting wording ("reported that …").
- **Thresholds** (0.55 strong, 0.35 weak) unchanged.
- **Persisted metric vocabulary** unchanged.

## 3. Comparability gate behaviour, by category
The gate checks, in order: assurance scope exclusions; named-measure agreement (company gross total, avoided/supplier programme, product footprint, facility coverage); material-content rules; all-versus-subset facility coverage; then modality, metric, baseline, organisational boundary, methodology and reporting period. A pair is `COMPATIBLE` only when every required element matches. Missing elements give `INCONCLUSIVE` with the missing items named.

## 4. Cross-company tests (synthetic)
New file `tests/test_cross_company_comparability.py` (15 tests) and `tests/test_company_disambiguation.py` (7) and `tests/test_company_configuration.py` (2). Each assertion checks the verdict **and** the reason phrase.
- Samsung: gross total vs supplier avoided → INCOMPATIBLE ("different measures"); compatible gross-vs-gross passes; baseline year change → INCOMPATIBLE; scope change → INCOMPATIBLE ("measurement scopes or boundaries differ").
- Microsoft: product footprint vs company Scope 3 → INCOMPATIBLE; datacenters vs supplier clean energy → INCOMPATIBLE; target vs achieved → INCOMPATIBLE ("Performance modalities differ").
- Tesla: recycled cobalt vs Scope 3 → INCOMPATIBLE (material content); recycled materials vs emissions total → INCOMPATIBLE; assurance excluding Scopes 1 and 3 → INCOMPATIBLE ("explicitly excludes"); compatible gross-vs-gross passes.
- Infosys: campuses vs supplier programme → INCOMPATIBLE; all facilities vs partial subset → INCOMPATIBLE ("subset of facilities"); table fragment → INCONCLUSIVE ("not extracted").
- Apple: the five regression scenarios remain in `tests/test_evidence_comparability.py` and `tests/test_matcher_comparability.py`.
- Concatenated heading text → INCONCLUSIVE (not promoted).

Against the previous delivered package, 3 of the new cross-company tests fail (campus, datacenter and gross-with-scope wording), so they detect real gaps that were fixed.

## 5. Before and after (fixed synthetic pair set, 17 pairs, gate verdicts)
| Verdict | Before (previous package) | After (current) |
|---|---|---|
| COMPATIBLE | 2 | 2 |
| INCOMPATIBLE | 11 | 14 |
| INCONCLUSIVE | 4 | 1 |

Changed pairs (all INCONCLUSIVE → INCOMPATIBLE, with a more specific reason): Samsung gross vs supplier; Microsoft datacenters vs supplier; Infosys campuses vs supplier. **No pair that was COMPATIBLE became incompatible.** The noisy-fragment case remains INCONCLUSIVE, as intended.
Note: the "before" package already contained the Apple-era fixes, so this is not a comparison against the original upload.

Matcher-level status (`potentially_relevant_evidence_found` vs `candidates_found_but_incompatible`) is produced from these verdicts and was verified in the earlier Apple-scenario tests; it was not re-tallied here.

## 6. Test results (sandbox)
| Run | Ran | Passed | Failures | Errors (missing package) | Skipped |
|---|---|---|---|---|---|
| E, no optional packages | 226 | 193 | 0 | 32 | 1 |
| F, with stubs (ddgs/pymupdf/plotly) | 261 | 246 | 0 | 14 | 1 |
No new errors compared with the previous run. Compile check of the project: exit 0. Stubs are sandbox-only and are not in the package.

## 7. Not verified / not done
- **Streamlit startup and UI**: not run. Not claimed.
- **Live collection, search aliases and query generation for each company**: not run. The web-search module cannot import here (needs `ddgs`), so its tests and alias derivation are blocked. Only the domain configuration shape was checked.
- **Persistence consistency across UI, database and saved analyses**: the UI now shares one analysis-level rule (`risk_summary.py`). The database stores per-claim rows and no analysis-level column, so end-to-end consistency was **not verified** against a real database. No database or saved analysis was in the sandbox; none was touched.
- **Duplicate and related sources; noisy PDF extraction in the live pipeline**: only the gate's handling of fragments was tested. Deduplication across different URLs for the same underlying report is not implemented.
- **Reviewer and assurance independence beyond scope exclusion** (for example, publisher versus author versus reviewer): not modelled.
- **Precision and recall**: not measured (no reviewed dataset).
- **Known conservative gaps**: a pair whose boundary is written in an unrecognised form (for example "Korean operations") returns `INCONCLUSIVE`, not `INCOMPATIBLE`. This never produces a false pass, but it can under-report incompatibility.

## 8. Required next steps (on your machine)
1. Install `requirements.txt` in the project `.venv`, then run the full suite.
2. Run the Streamlit app and confirm it starts.
3. For each of Apple, Samsung, Microsoft, Tesla and Infosys: run one analysis, then compare candidate counts by status with the same claims from before this change. Keep the saved analyses; do not overwrite them.
4. Build a small human-reviewed set of claim–evidence pairs before reporting any accuracy figure.
